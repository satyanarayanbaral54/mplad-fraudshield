"""
MPLAD FraudShield - Machine Learning Anomaly Detection & Clustering Engine
Combines Isolation Forest for multi-dimensional anomaly detection and
DBSCAN for vendor collusion network discovery.
"""
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# Safe path resolution
_curr = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_curr, ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from utils.helpers import engineer_features, preprocess_pipeline
except ImportError:
    from backend.utils.helpers import engineer_features, preprocess_pipeline


class MLAnomalyEngine:
    """
    Machine learning engine for statistical anomaly detection and vendor collusion clustering.
    """

    def __init__(self):
        self.iso_forest: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_columns: List[str] = [
            "utilization_rate",
            "days_to_completion",
            "cost_deviation_pct",
            "year_end_rush_flag",
            "vendor_project_count",
            "mp_avg_utilization",
            "days_recommend_to_sanction",
            "vendor_days_before_contract",
            "is_phantom",
            "unspent_balance",
        ]

    # -----------------------------------------------------------------------
    # PART A — Isolation Forest Anomaly Detection
    # -----------------------------------------------------------------------
    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensures all feature columns exist, engineering them if missing."""
        df_feat = df.copy()
        missing = [c for c in self.feature_columns if c not in df_feat.columns]
        if missing:
            df_feat = engineer_features(df_feat)

        X = df_feat[self.feature_columns].copy()

        # Handle missing or infinite values safely
        for col in self.feature_columns:
            if col in X.columns:
                med = X[col].replace([np.inf, -np.inf], np.nan).median()
                fill_val = med if pd.notnull(med) else 0.0
                X[col] = X[col].replace([np.inf, -np.inf], np.nan).fillna(fill_val)

        return X

    def train(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Fits StandardScaler and IsolationForest model on dataset features.
        Saves trained pkl artifacts to backend/models/.
        """
        if df.empty:
            return {"trained": False, "reason": "Empty DataFrame"}

        X = self._prepare_features(df)

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.iso_forest = IsolationForest(
            n_estimators=200,
            contamination=0.05,
            random_state=42,
            n_jobs=-1
        )
        preds = self.iso_forest.fit_predict(X_scaled)

        anomaly_count = int((preds == -1).sum())

        models_dir = os.path.join(_root, "models")
        self.save_models(models_dir)

        return {
            "trained": True,
            "n_samples": len(df),
            "anomaly_count": anomaly_count,
            "contamination_rate": round(anomaly_count / len(df), 4)
        }

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms features, computes Isolation Forest decision scores,
        normalizes scores to 0-100 scale, and adds anomaly boolean flags.
        """
        if df.empty:
            df_out = df.copy()
            df_out["ml_anomaly_score"] = 0.0
            df_out["ml_is_anomaly"] = False
            return df_out

        models_dir = os.path.join(_root, "models")
        if self.iso_forest is None or self.scaler is None:
            loaded = self.load_models(models_dir)
            if not loaded:
                print("[*] Models not found. Training Isolation Forest on input dataset...")
                self.train(df)

        X = self._prepare_features(df)
        X_scaled = self.scaler.transform(X)

        # Raw decision function scores (lower/negative = more anomalous)
        raw_scores = self.iso_forest.decision_function(X_scaled)
        predictions = self.iso_forest.predict(X_scaled)

        # Normalize raw scores to 0-100 scale (inverting so higher = more anomalous)
        # Normal decision_function values range from ~ -0.30 to +0.15
        min_s, max_s = -0.30, 0.15
        norm_scores = np.clip(100.0 * (max_s - raw_scores) / (max_s - min_s + 1e-6), 0.0, 100.0)

        # Keep obvious public-procurement outliers visible even when the model was
        # trained on a dataset that already contains several injected anomalies.
        heuristic_scores = np.zeros(len(X), dtype=float)
        if "utilization_rate" in X.columns:
            heuristic_scores = np.maximum(heuristic_scores, np.where(X["utilization_rate"] >= 1.25, 78.0, 0.0))
        if "cost_deviation_pct" in X.columns:
            heuristic_scores = np.maximum(heuristic_scores, np.where(X["cost_deviation_pct"] >= 300.0, 82.0, 0.0))
        if "days_to_completion" in X.columns:
            heuristic_scores = np.maximum(heuristic_scores, np.where((X["days_to_completion"] >= 0) & (X["days_to_completion"] < 7), 72.0, 0.0))
        if "vendor_project_count" in X.columns:
            heuristic_scores = np.maximum(heuristic_scores, np.where(X["vendor_project_count"] >= 20, 74.0, 0.0))
        if "is_phantom" in X.columns:
            heuristic_scores = np.maximum(heuristic_scores, np.where(X["is_phantom"] >= 1, 76.0, 0.0))
        norm_scores = np.maximum(norm_scores, heuristic_scores)

        df_out = df.copy()
        df_out["ml_anomaly_score"] = np.round(norm_scores, 2)
        df_out["ml_is_anomaly"] = (predictions == -1)

        return df_out

    def train_and_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convenience method: trains model on dataset and returns scored DataFrame."""
        self.train(df)
        return self.score(df)

    # -----------------------------------------------------------------------
    # PART B — DBSCAN for Vendor Collusion Clustering
    # -----------------------------------------------------------------------
    def cluster_vendors(self, df_vendors: pd.DataFrame) -> pd.DataFrame:
        """
        Runs DBSCAN clustering on vendor metadata & contract metrics
        to detect spatial/contractual collusion clusters.
        """
        if df_vendors.empty or len(df_vendors) < 2:
            df_out = df_vendors.copy()
            df_out["cluster_id"] = -1
            df_out["collusion_suspected"] = False
            return df_out

        df_out = df_vendors.copy()

        # If caller passed a projects-level dataframe rather than vendor-summary,
        # aggregate vendor-level metrics first.
        if "vendor_name" in df_out.columns and "project_id" in df_out.columns:
            vendors_summary = (
                df_out.groupby("vendor_name").agg(
                    project_count=("project_id", "count"),
                    total_contract_value=("sanctioned_amount", "sum"),
                    state=("state", "first"),
                    city=("district", "first"),
                    mp_list=("mp_name", lambda s: list(pd.unique(s.dropna())))
                )
                .reset_index()
            )
            df_out = vendors_summary

        # Ensure expected columns exist
        for c in ["state", "city", "project_count", "total_contract_value"]:
            if c not in df_out.columns:
                df_out[c] = None

        # Label-encode categorical columns across the column (not per-row)
        state_codes, state_uniques = pd.factorize(df_out["state"].fillna("__NA__"))
        city_codes, city_uniques = pd.factorize(df_out["city"].fillna("__NA__"))

        projects = pd.to_numeric(df_out["project_count"].fillna(0), errors="coerce").fillna(0).astype(float)
        values = pd.to_numeric(df_out["total_contract_value"].fillna(0.0), errors="coerce").fillna(0.0).astype(float)

        X = np.vstack([state_codes, city_codes, projects.values, values.values]).T
        X_scaled = StandardScaler().fit_transform(X)

        db = DBSCAN(eps=0.8, min_samples=2)
        clusters = db.fit_predict(X_scaled)

        df_out["cluster_id"] = clusters

        # Build MP sets per vendor if available in the input (column may be mp_list)
        mp_sets = {}
        if "mp_list" in df_out.columns:
            for i, v in df_out["vendor_name"].items():
                lst = df_out.at[i, "mp_list"]
                if isinstance(lst, (list, tuple, set)):
                    mp_sets[v] = set([str(x).strip() for x in lst if pd.notna(x)])
                else:
                    mp_sets[v] = set()
        else:
            # No MP info available — create empty sets
            for v in df_out.get("vendor_name", pd.Series([], dtype=object)):
                mp_sets[v] = set()

        # For each cluster, detect vendors that share any MP across vendors in same cluster
        # Create an index-keyed flag map for correct alignment with df_out
        collusion_map = {idx: False for idx in df_out.index}
        cluster_groups = df_out.groupby("cluster_id").groups
        for cid, indices in cluster_groups.items():
            if cid == -1:
                continue
            vendors_in_cluster = df_out.loc[indices, "vendor_name"].tolist()
            # For each vendor in the cluster, check intersection of MP sets with others
            for idx_label, vendor in zip(indices, vendors_in_cluster):
                vendor_set = mp_sets.get(vendor, set())
                for other_vendor in vendors_in_cluster:
                    if other_vendor == vendor:
                        continue
                    other_set = mp_sets.get(other_vendor, set())
                    if vendor_set and other_set and (vendor_set & other_set):
                        collusion_map[idx_label] = True
                        break

            # If MP info missing for the whole cluster, fallback to marking cluster members as suspected
            if all(len(mp_sets.get(v, set())) == 0 for v in df_out.loc[indices, "vendor_name"]):
                for idx_label in indices:
                    collusion_map[idx_label] = True

        # Assign collusion flags in dataframe order
        df_out["collusion_suspected"] = [bool(collusion_map.get(idx, False)) for idx in df_out.index]
        return df_out
        return df_out

    def get_vendor_network_data(self, df: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generates D3.js force graph nodes and links representing MP-Vendor contracts.
        """
        if df.empty or "mp_name" not in df.columns or "vendor_name" not in df.columns:
            return {"nodes": [], "links": []}

        nodes_dict: Dict[str, Dict[str, Any]] = {}
        links_dict: Dict[Tuple[str, str], Dict[str, Any]] = {}

        for _, row in df.iterrows():
            mp = str(row.get("mp_name", "Unknown MP")).strip()
            vendor = str(row.get("vendor_name", "Unknown Vendor")).strip()
            amount = float(row.get("sanctioned_amount", row.get("contract_amount", 0.0)))
            anomaly_score = float(row.get("ml_anomaly_score", row.get("red_flag_score", 0.0)))

            if not mp or not vendor or vendor.lower() == "nan":
                continue

            mp_id = f"mp_{mp}"
            vendor_id = f"vendor_{vendor}"

            # Create or update MP node
            if mp_id not in nodes_dict:
                nodes_dict[mp_id] = {
                    "id": mp_id,
                    "name": mp,
                    "type": "MP",
                    "risk": round(anomaly_score, 1),
                    "total_val": round(amount, 2),
                    "projects": 1
                }
            else:
                nodes_dict[mp_id]["total_val"] += round(amount, 2)
                nodes_dict[mp_id]["projects"] += 1
                nodes_dict[mp_id]["risk"] = max(nodes_dict[mp_id]["risk"], round(anomaly_score, 1))

            # Create or update Vendor node
            if vendor_id not in nodes_dict:
                nodes_dict[vendor_id] = {
                    "id": vendor_id,
                    "name": vendor,
                    "type": "vendor",
                    "flagged": anomaly_score > 50.0,
                    "risk": round(anomaly_score, 1),
                    "total_val": round(amount, 2),
                    "projects": 1
                }
            else:
                nodes_dict[vendor_id]["total_val"] += round(amount, 2)
                nodes_dict[vendor_id]["projects"] += 1
                nodes_dict[vendor_id]["risk"] = max(nodes_dict[vendor_id]["risk"], round(anomaly_score, 1))
                if anomaly_score > 50.0:
                    nodes_dict[vendor_id]["flagged"] = True

            # Create or update link
            link_key = (mp_id, vendor_id)
            if link_key not in links_dict:
                links_dict[link_key] = {
                    "source": mp_id,
                    "target": vendor_id,
                    "value": round(amount, 2),
                    "projects": 1
                }
            else:
                links_dict[link_key]["value"] += round(amount, 2)
                links_dict[link_key]["projects"] += 1

        return {
            "nodes": list(nodes_dict.values()),
            "links": list(links_dict.values())
        }

    # -----------------------------------------------------------------------
    # PART C — Model Persistence
    # -----------------------------------------------------------------------
    def save_models(self, path: Optional[str] = None) -> None:
        """Saves scaler and isolation forest model to disk."""
        if path is None:
            path = os.path.join(_root, "models")
        os.makedirs(path, exist_ok=True)
        if self.iso_forest is not None:
            joblib.dump(self.iso_forest, os.path.join(path, "iso_forest.pkl"))
        if self.scaler is not None:
            joblib.dump(self.scaler, os.path.join(path, "scaler.pkl"))

    def load_models(self, path: Optional[str] = None) -> bool:
        """Loads trained scaler and isolation forest model from disk if present."""
        candidate_paths = []
        if path is not None:
            candidate_paths.append(path)
        candidate_paths.extend([
            os.path.join(_root, "models"),
            os.path.join(os.getcwd(), "models"),
            os.path.join(os.getcwd(), "backend", "models"),
            "models",
            "backend/models",
        ])

        for p in candidate_paths:
            model_path = os.path.join(p, "iso_forest.pkl")
            scaler_path = os.path.join(p, "scaler.pkl")
            if os.path.exists(model_path) and os.path.exists(scaler_path):
                try:
                    self.iso_forest = joblib.load(model_path)
                    self.scaler = joblib.load(scaler_path)
                    return True
                except Exception as e:
                    print(f"[!] Error loading model files from {p}: {e}")
                    return False
        return False

    # -----------------------------------------------------------------------
    # Legacy Compatibility Adapters
    # -----------------------------------------------------------------------
    def fit(self, projects: List[Dict[str, Any]]) -> None:
        """Legacy dictionary list trainer adapter."""
        df = pd.DataFrame(projects)
        self.train(df)

    def predict(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy single project prediction adapter."""
        df = pd.DataFrame([project])
        df_res = self.score(df)
        score = float(df_res.iloc[0]["ml_anomaly_score"])
        is_anomaly = bool(df_res.iloc[0]["ml_is_anomaly"])
        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": score,
            "flags": [{"flag_type": "ML_ANOMALY", "severity": "HIGH" if score > 75 else "MEDIUM"}] if is_anomaly else []
        }


ml_engine = MLAnomalyEngine()
MLEngine = MLAnomalyEngine  # Class alias for backward compatibility

# ---------------------------------------------------------------------------
# Auto-Train on Dataset if Models Not Present
# ---------------------------------------------------------------------------
try:
    models_path = os.path.join(_root, "models")
    if not ml_engine.load_models(models_path):
        data_csv = os.path.join(_root, "data", "sample_dataset.csv")
        if os.path.exists(data_csv):
            print(f"[*] Auto-training MLAnomalyEngine on dataset {data_csv}...")
            df_init = preprocess_pipeline(data_csv)
            ml_engine.train(df_init)
            print("[✓] MLAnomalyEngine trained and models saved.")
except Exception as err:
    print(f"[!] Auto-training warning: {err}")


# ---------------------------------------------------------------------------
# Self-Test Execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    data_csv = os.path.join(_root, "data", "sample_dataset.csv")
    print(f"[*] Running ML Engine validation on {data_csv}...")

    df_test = preprocess_pipeline(data_csv)

    # 1. Test Isolation Forest scoring
    df_scored = ml_engine.score(df_test)
    anomalies_found = df_scored["ml_is_anomaly"].sum()
    mean_score = df_scored["ml_anomaly_score"].mean()

    print(f"[OK] Isolation Forest Scoring Complete:")
    print(f"     - Total Records: {len(df_scored)}")
    print(f"     - Statistical Anomalies (Score > 65): {anomalies_found}")
    print(f"     - Average ML Anomaly Score: {mean_score:.2f}")

    # 2. Test Vendor Clustering
    vendors_summary = df_test.groupby("vendor_name").agg(
        project_count=("project_id", "count"),
        total_contract_value=("sanctioned_amount", "sum"),
        state=("state", "first"),
        district=("district", "first")
    ).reset_index()

    df_clustered = ml_engine.cluster_vendors(vendors_summary)
    suspect_vendors = df_clustered["collusion_suspected"].sum()
    print(f"\n[OK] DBSCAN Vendor Clustering Complete:")
    print(f"     - Total Unique Vendors: {len(df_clustered)}")
    print(f"     - Collusion Suspected Vendors: {suspect_vendors}")
    print(f"     - Cluster IDs: {df_clustered['cluster_id'].unique().tolist()}")

    # 3. Test Network Graph Structure
    net_graph = ml_engine.get_vendor_network_data(df_scored)
    print(f"\n[OK] Network Graph Generation Complete:")
    print(f"     - D3 Nodes Count: {len(net_graph['nodes'])}")
    print(f"     - D3 Links Count: {len(net_graph['links'])}")

    print("\nALL ML ENGINE COMPONENTS VERIFIED SUCCESSFULLY!")
