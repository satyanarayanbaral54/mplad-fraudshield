"""
OpenStreetMap geospatial verification for MPLAD projects.

Uses the Overpass API through overpy to check whether completed projects have
nearby map features matching the reported work type.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd

try:
    import overpy
except ImportError:  # pragma: no cover - dependency is optional at import time
    overpy = None

logger = logging.getLogger(__name__)


class GeoVerificationEngine:
    """Verify reported infrastructure against OpenStreetMap features."""

    OSM_TAG_MAP = {
        "road": "highway",
        "school": "amenity=school",
        "hospital": "amenity=hospital",
        "well": "man_made=water_well",
        "community_hall": "amenity=community_centre",
        "bridge": "man_made=bridge",
        "other": "building",
    }

    def __init__(self) -> None:
        self.api = overpy.Overpass() if overpy is not None else None

    def verify_project_location(self, lat: float, lon: float, work_type: str, radius: int = 100) -> Dict[str, Any]:
        """
        Query Overpass for OSM features matching work_type near lat/lon.

        Returns:
            {
              "status": "VERIFIED"|"NOT_FOUND"|"ERROR",
              "osm_features_found": int,
              "nearest_feature": str or None,
              "confidence": "HIGH"|"MEDIUM"|"LOW"
            }
        """
        if self.api is None or overpy is None:
            return {
                "status": "ERROR",
                "osm_features_found": 0,
                "nearest_feature": None,
                "confidence": "LOW",
                "error": "overpy is not installed",
            }

        try:
            lat_value = float(lat)
            lon_value = float(lon)
        except (TypeError, ValueError):
            return {
                "status": "ERROR",
                "osm_features_found": 0,
                "nearest_feature": None,
                "confidence": "LOW",
                "error": "Invalid latitude/longitude",
            }

        if not (-90 <= lat_value <= 90 and -180 <= lon_value <= 180):
            return {
                "status": "ERROR",
                "osm_features_found": 0,
                "nearest_feature": None,
                "confidence": "LOW",
                "error": "Latitude/longitude out of range",
            }

        radius = max(1, int(radius))
        query = self._build_query(lat_value, lon_value, work_type, radius)

        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                result = self._query_overpass(query)
                features = self._collect_features(result)
                features_found = len(features)
                nearest_feature = features[0] if features else None

                return {
                    "status": "VERIFIED" if features_found > 0 else "NOT_FOUND",
                    "osm_features_found": features_found,
                    "nearest_feature": nearest_feature,
                    "confidence": self._confidence(features_found),
                }
            except (overpy.exception.OverPyException, TimeoutError, URLError, OSError) as exc:
                last_error = exc
                logger.warning("Overpass query failed on attempt %d/2: %s", attempt + 1, exc)
                if attempt == 0:
                    time.sleep(3)

        return {
            "status": "ERROR",
            "osm_features_found": 0,
            "nearest_feature": None,
            "confidence": "LOW",
            "error": str(last_error) if last_error else "Overpass query failed",
        }

    def batch_verify(self, df: pd.DataFrame, max_verifications: int = 50) -> pd.DataFrame:
        """
        Verify completed projects whose geo_verification_status is pending.

        The number of Overpass calls is capped to avoid rate limiting. A one
        second pause is added between calls.
        """
        result = df.copy()
        if result.empty:
            if "geo_verification_status" not in result.columns:
                result["geo_verification_status"] = pd.Series(dtype=object)
            return result

        if "geo_verification_status" not in result.columns:
            result["geo_verification_status"] = "pending"

        required = {"latitude", "longitude", "work_type", "status", "geo_verification_status"}
        if not required.issubset(result.columns):
            missing = sorted(required - set(result.columns))
            raise ValueError(f"Missing required columns for geo verification: {missing}")

        completed = result["status"].fillna("").astype(str).str.casefold() == "completed"
        pending = result["geo_verification_status"].fillna("pending").astype(str).str.casefold() == "pending"
        candidate_indices = result[completed & pending].head(max(0, int(max_verifications))).index.tolist()

        for position, index in enumerate(candidate_indices):
            row = result.loc[index]
            verification = self.verify_project_location(
                lat=row["latitude"],
                lon=row["longitude"],
                work_type=str(row.get("work_type", "other")),
            )

            result.at[index, "geo_verification_status"] = verification["status"]
            result.at[index, "geo_osm_features_found"] = verification["osm_features_found"]
            result.at[index, "geo_nearest_feature"] = verification["nearest_feature"]
            result.at[index, "geo_confidence"] = verification["confidence"]
            if verification.get("error"):
                result.at[index, "geo_error"] = verification["error"]

            if position < len(candidate_indices) - 1:
                time.sleep(1)

        return result

    def get_map_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Return normalized project records for Leaflet map rendering."""
        map_data: List[Dict[str, Any]] = []
        if df.empty:
            return map_data

        for _, row in df.iterrows():
            lat = self._to_float(row.get("latitude", row.get("lat")))
            lon = self._to_float(row.get("longitude", row.get("lon")))
            if lat is None or lon is None:
                continue

            map_data.append({
                "project_id": self._clean_value(row.get("project_id", row.get("id", ""))),
                "lat": lat,
                "lon": lon,
                "work_name": self._clean_value(row.get("title", row.get("work_name", row.get("work_type", "")))),
                "work_type": self._clean_value(row.get("work_type", "")),
                "risk_level": self._clean_value(row.get("risk_level", "LOW")),
                "risk_score": self._to_float(row.get("final_risk_score", row.get("risk_score", 0.0))) or 0.0,
                "mp_name": self._clean_value(row.get("mp_name", "")),
                "amount": self._to_float(row.get("sanctioned_amount", row.get("allocated_amount", row.get("amount", 0.0)))) or 0.0,
                "status": self._clean_value(row.get("status", "")),
                "geo_status": self._clean_value(row.get("geo_verification_status", row.get("geo_status", "pending"))),
                "flags_count": self._flags_count(row),
            })

        return map_data

    def verify_infrastructure(self, project: Dict[str, Any], latitude: float, longitude: float) -> Dict[str, Any]:
        """Backward-compatible adapter for the previous GeoEngine API."""
        work_type = str(project.get("work_type") or project.get("title") or project.get("description") or "other")
        verification = self.verify_project_location(latitude, longitude, work_type, radius=500)
        verified = verification["status"] == "VERIFIED"
        flags = []
        if verification["status"] == "NOT_FOUND":
            flags.append({
                "flag_type": "GEO_INFRASTRUCTURE_NOT_FOUND",
                "severity": "HIGH",
                "description": "No matching OSM infrastructure found near reported coordinates.",
                "engine_source": "GeoVerificationEngine",
                "evidence": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "osm_features_found": verification["osm_features_found"],
                    "confidence": verification["confidence"],
                },
            })

        return {
            "verified": verified if verification["status"] != "ERROR" else None,
            "osm_data": {
                "features_found": verification["osm_features_found"],
                "nearest_feature": verification["nearest_feature"],
            },
            "flags": flags,
            **({"error": verification.get("error")} if verification.get("error") else {}),
        }

    def _build_query(self, lat: float, lon: float, work_type: str, radius: int) -> str:
        key, value = self._tag_for_work_type(work_type)
        if value is None:
            selectors = [
                f'node["{key}"](around:{radius},{lat},{lon});',
                f'way["{key}"](around:{radius},{lat},{lon});',
                f'relation["{key}"](around:{radius},{lat},{lon});',
            ]
        else:
            selectors = [
                f'node["{key}"="{value}"](around:{radius},{lat},{lon});',
                f'way["{key}"="{value}"](around:{radius},{lat},{lon});',
                f'relation["{key}"="{value}"](around:{radius},{lat},{lon});',
            ]

        return "[out:json][timeout:15];\n(\n  " + "\n  ".join(selectors) + "\n);\nout tags center;"

    def _query_overpass(self, query: str) -> Any:
        data = urlencode({"data": query}).encode("utf-8")
        request = Request(
            "https://overpass-api.de/api/interpreter",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": "MPLAD-FraudShield/1.0",
            },
            method="POST",
        )
        with urlopen(request, timeout=15) as response:
            payload = response.read().decode("utf-8")
        return self.api.parse_json(payload)

    def _tag_for_work_type(self, work_type: str) -> Tuple[str, Optional[str]]:
        normalized = str(work_type or "").lower().replace("-", " ").replace("&", " ")
        normalized = " ".join(normalized.split())

        if any(term in normalized for term in ["road", "culvert", "drainage canal"]):
            tag = self.OSM_TAG_MAP["road"]
        elif any(term in normalized for term in ["school", "classroom", "library", "smart class"]):
            tag = self.OSM_TAG_MAP["school"]
        elif any(term in normalized for term in ["hospital", "health", "clinic"]):
            tag = self.OSM_TAG_MAP["hospital"]
        elif any(term in normalized for term in ["well", "borewell", "drinking water", "water supply"]):
            tag = self.OSM_TAG_MAP["well"]
        elif any(term in normalized for term in ["community hall", "community centre", "community center", "shelter"]):
            tag = self.OSM_TAG_MAP["community_hall"]
        elif "bridge" in normalized:
            tag = self.OSM_TAG_MAP["bridge"]
        else:
            tag = self.OSM_TAG_MAP["other"]

        if "=" in tag:
            key, value = tag.split("=", 1)
            return key, value
        return tag, None

    @staticmethod
    def _collect_features(result: Any) -> List[str]:
        features: List[str] = []
        for collection_name in ("nodes", "ways", "relations"):
            for element in getattr(result, collection_name, []):
                tags = getattr(element, "tags", {}) or {}
                name = tags.get("name")
                feature_type = tags.get("amenity") or tags.get("highway") or tags.get("man_made") or tags.get("building")
                if name and feature_type:
                    features.append(f"{name} ({feature_type})")
                elif name:
                    features.append(str(name))
                elif feature_type:
                    features.append(str(feature_type))
                else:
                    element_id = getattr(element, "id", "unknown")
                    features.append(f"{collection_name[:-1]}:{element_id}")
        return features

    @staticmethod
    def _confidence(features_found: int) -> str:
        if features_found >= 3:
            return "HIGH"
        if features_found >= 1:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            if pd.isna(value):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_value(value: Any) -> Any:
        if pd.isna(value):
            return ""
        return value.item() if hasattr(value, "item") else value

    @staticmethod
    def _flags_count(row: pd.Series) -> int:
        flags = row.get("flags_triggered", [])
        if isinstance(flags, (list, tuple, set)):
            return len(flags)
        if pd.notna(flags) and str(flags).strip():
            return len([part for part in str(flags).split(",") if part.strip()])
        return 0


class GeoEngine(GeoVerificationEngine):
    """Backward-compatible class name for older imports."""


geo_verification_engine = GeoVerificationEngine()
geo_engine = geo_verification_engine
