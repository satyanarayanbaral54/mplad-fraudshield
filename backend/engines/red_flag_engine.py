"""
MPLAD FraudShield - Deterministic Rule-Based Red Flag Engine
Fast, accurate forensic fraud detection for MPLAD public infrastructure projects.
"""
import math
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

# Safe path resolution
_curr = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_curr, ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates geodesic distance between two GPS points in meters."""
    R = 6371000.0  # Radius of earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


FLAG_EXPLANATION_TEMPLATES = {
    "duplicate_gps": "Duplicate GPS Location: Infrastructure project shares physical coordinates (<50m) with another sanctioned project, indicating potential ghost duplicate billing.",
    "repeated_vendor": "Vendor Cartelization: Single contractor monopolizing multiple projects from the same MP, indicating non-competitive tendering.",
    "cost_outlier": "Inflated Cost Outlier: Sanctioned expenditure exceeds the state CPWD benchmark by over 150%.",
    "year_end_rush": "Fiscal Year-End Rush: Panic fund utilization (>60% of annual quota) concentrated in February-March before fiscal closure.",
    "phantom_completion": "Phantom Completion: Project marked completed in portal records without photographic site proof.",
    "fast_completion": "Physically Impossible Timeline: Civil construction marked complete in under 30 days.",
    "shell_vendor": "Shell Contractor: Vendor registered less than 6 months prior to receiving high-value contract award.",
    "fund_recycling": "Cross-MP Fund Recycling: Identical work at duplicate GPS coordinates funded across different MP quotas.",
}


class RedFlagEngine:
    """
    Forensic rule engine that evaluates 8 deterministic public procurement red flags.
    """

    RULE_WEIGHTS = {
        "duplicate_gps": 30,
        "repeated_vendor": 20,
        "cost_outlier": 25,
        "year_end_rush": 15,
        "phantom_completion": 35,
        "fast_completion": 25,
        "shell_vendor": 30,
        "fund_recycling": 40,
    }

    # -----------------------------------------------------------------------
    # Rule 1: Duplicate GPS (< 50m)
    # -----------------------------------------------------------------------
    def rule_duplicate_gps(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """Finds pairs of projects within 50m radius (potential duplicate billing)."""
        flags: Dict[str, Dict[str, Any]] = {}
        if df.empty or "latitude" not in df.columns or "longitude" not in df.columns:
            return flags

        valid = df[df["latitude"].notnull() & df["longitude"].notnull() & (df["latitude"] != 0) & (df["longitude"] != 0)].copy()
        if len(valid) < 2:
            return flags

        group_col = "district" if "district" in valid.columns else "state"
        groups = valid.groupby(group_col) if group_col in valid.columns else [("all", valid)]

        for _, group in groups:
            records = group[["project_id", "latitude", "longitude"]].to_dict("records")
            n = len(records)
            for i in range(n):
                p1 = records[i]
                for j in range(i + 1, n):
                    p2 = records[j]
                    dist = haversine_meters(p1["latitude"], p1["longitude"], p2["latitude"], p2["longitude"])
                    if dist <= 50.0:
                        detail_1 = f"Project {p1['project_id']} and Project {p2['project_id']} share GPS coordinates within 50m radius ({dist:.1f}m) — possible duplicate billing"
                        detail_2 = f"Project {p2['project_id']} and Project {p1['project_id']} share GPS coordinates within 50m radius ({dist:.1f}m) — possible duplicate billing"
                        
                        flags[p1["project_id"]] = {
                            "flag_name": "duplicate_gps",
                            "detail": detail_1,
                            "weight": self.RULE_WEIGHTS["duplicate_gps"],
                            "evidence": {"duplicate_with": p2["project_id"], "distance_meters": round(dist, 1)}
                        }
                        flags[p2["project_id"]] = {
                            "flag_name": "duplicate_gps",
                            "detail": detail_2,
                            "weight": self.RULE_WEIGHTS["duplicate_gps"],
                            "evidence": {"duplicate_with": p1["project_id"], "distance_meters": round(dist, 1)}
                        }
        return flags

    # -----------------------------------------------------------------------
    # Rule 2: Repeated Vendor (3+ projects from same MP)
    # -----------------------------------------------------------------------
    def rule_repeated_vendor(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """Flags vendors winning 3 or more projects from the same MP (collusion/cartel)."""
        flags: Dict[str, Dict[str, Any]] = {}
        if df.empty or "vendor_name" not in df.columns or "mp_name" not in df.columns:
            return flags

        grouped = df.groupby(["mp_name", "vendor_name"])
        for (mp_name, vendor_name), group in grouped:
            if pd.isnull(vendor_name) or str(vendor_name).strip() == "":
                continue
            count = len(group)
            if count >= 3:
                total_val = group["sanctioned_amount"].sum() if "sanctioned_amount" in group.columns else 0.0
                detail = f"Vendor '{vendor_name}' has won {count} contracts worth ₹{total_val:,.2f} Lakhs from MP {mp_name} — pattern suggests non-competitive award"
                for pid in group["project_id"]:
                    flags[pid] = {
                        "flag_name": "repeated_vendor",
                        "detail": detail,
                        "weight": self.RULE_WEIGHTS["repeated_vendor"],
                        "evidence": {"vendor_name": vendor_name, "mp_name": mp_name, "contracts_count": count, "total_value_lakhs": round(total_val, 2)}
                    }
        return flags

    # -----------------------------------------------------------------------
    # Rule 3: Cost Outlier (> 150% above State Benchmark)
    # -----------------------------------------------------------------------
    def rule_cost_outlier(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """Flags projects where cost per unit is > 150% above the state average benchmark."""
        flags: Dict[str, Dict[str, Any]] = {}
        if df.empty:
            return flags

        for _, row in df.iterrows():
            pid = row.get("project_id")
            dev_pct = row.get("cost_deviation_pct", 0.0)
            cost_unit = row.get("cost_per_unit", row.get("sanctioned_amount", 0.0))
            benchmark = row.get("state_benchmark", 25.0)
            work_type = row.get("work_type", "Civil Work")
            state = row.get("state", "State")

            if pd.notnull(dev_pct) and dev_pct > 150.0:
                detail = f"Cost ₹{cost_unit:,.2f} Lakhs/unit vs state average ₹{benchmark:,.2f} Lakhs/unit for {work_type} in {state} — {dev_pct:.1f}% above benchmark"
                flags[pid] = {
                    "flag_name": "cost_outlier",
                    "detail": detail,
                    "weight": self.RULE_WEIGHTS["cost_outlier"],
                    "evidence": {"cost_per_unit": cost_unit, "state_benchmark": benchmark, "deviation_pct": round(dev_pct, 1)}
                }
        return flags

    # -----------------------------------------------------------------------
    # Rule 4: Year-End Rush (Feb-March expenditure > 60% of MP's annual total)
    # -----------------------------------------------------------------------
    def rule_year_end_rush(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """Flags projects when MP's Feb-March utilization exceeds 60% of annual budget."""
        flags: Dict[str, Dict[str, Any]] = {}
        if df.empty or "mp_name" not in df.columns:
            return flags

        for mp_name, group in df.groupby("mp_name"):
            total_exp = group["expenditure_reported"].sum() if "expenditure_reported" in group.columns else 0.0
            if total_exp <= 0:
                continue

            rush_projects = group[group["year_end_rush_flag"] == 1] if "year_end_rush_flag" in group.columns else group[group["completion_month"].isin([2, 3])]
            rush_exp = rush_projects["expenditure_reported"].sum() if "expenditure_reported" in rush_projects.columns else 0.0

            rush_pct = (rush_exp / total_exp) * 100.0 if total_exp > 0 else 0.0

            if rush_pct > 60.0 or len(rush_projects) >= 4:
                for _, row in rush_projects.iterrows():
                    pid = row["project_id"]
                    detail = f"₹{rush_exp:,.2f} Lakhs ({rush_pct:.1f}%) of annual MPLAD funds utilized in Feb-March for MP {mp_name} — financial year-end panic spending pattern"
                    flags[pid] = {
                        "flag_name": "year_end_rush",
                        "detail": detail,
                        "weight": self.RULE_WEIGHTS["year_end_rush"],
                        "evidence": {"mp_name": mp_name, "feb_march_exp_lakhs": round(rush_exp, 2), "rush_percentage": round(rush_pct, 1)}
                    }
        return flags

    # -----------------------------------------------------------------------
    # Rule 5: Phantom Completion (Completed but no photos submitted)
    # -----------------------------------------------------------------------
    def rule_phantom_completion(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """Flags projects marked 'Completed' without photographic verification."""
        flags: Dict[str, Dict[str, Any]] = {}
        if df.empty:
            return flags

        for _, row in df.iterrows():
            pid = row.get("project_id")
            status = str(row.get("status", "")).strip().lower()
            has_photo = bool(row.get("has_photo", False))
            photo_urls = str(row.get("photo_urls", "")).strip()
            comp_date = str(row.get("completion_date", "recent date"))

            if status == "completed" and (not has_photo or photo_urls == "" or photo_urls.lower() == "nan"):
                detail = f"Project marked 'Completed' on {comp_date} but zero photos/proof of completion submitted to portal"
                flags[pid] = {
                    "flag_name": "phantom_completion",
                    "detail": detail,
                    "weight": self.RULE_WEIGHTS["phantom_completion"],
                    "evidence": {"status": "Completed", "has_photo": False}
                }
        return flags

    # -----------------------------------------------------------------------
    # Rule 6: Fast Completion (< 30 days for construction)
    # -----------------------------------------------------------------------
    def rule_fast_completion(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """Flags civil/construction works completed in under 30 days."""
        flags: Dict[str, Dict[str, Any]] = {}
        if df.empty:
            return flags

        for _, row in df.iterrows():
            pid = row.get("project_id")
            days = row.get("days_to_completion", -1)
            work_type = str(row.get("work_type", "Civil Construction"))
            work_name = str(row.get("title", work_type))

            if pd.notnull(days) and 0 <= days < 30:
                detail = f"Work '{work_name}' ({work_type}) completed in {int(days)} days — physically impossible for this work category"
                flags[pid] = {
                    "flag_name": "fast_completion",
                    "detail": detail,
                    "weight": self.RULE_WEIGHTS["fast_completion"],
                    "evidence": {"days_to_completion": int(days), "work_type": work_type}
                }
        return flags

    # -----------------------------------------------------------------------
    # Rule 7: Shell Vendor (Registered < 6 months / 180 days before contract)
    # -----------------------------------------------------------------------
    def rule_shell_vendor(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """Flags contracts awarded to newly registered vendors (< 180 days)."""
        flags: Dict[str, Dict[str, Any]] = {}
        if df.empty:
            return flags

        for _, row in df.iterrows():
            pid = row.get("project_id")
            days_before = row.get("vendor_days_before_contract", -1)
            vendor = str(row.get("vendor_name", "Vendor"))
            contract_val = row.get("sanctioned_amount", row.get("contract_amount", 0.0))

            if pd.notnull(days_before) and 0 <= days_before < 180:
                detail = f"Vendor '{vendor}' registered only {int(days_before)} days before receiving ₹{contract_val:,.2f} Lakh contract — possible shell company"
                flags[pid] = {
                    "flag_name": "shell_vendor",
                    "detail": detail,
                    "weight": self.RULE_WEIGHTS["shell_vendor"],
                    "evidence": {"vendor_name": vendor, "registration_lead_days": int(days_before), "contract_value_lakhs": contract_val}
                }
        return flags

    # -----------------------------------------------------------------------
    # Rule 8: Fund Recycling (Same work + GPS < 200m under 2 different MPs)
    # -----------------------------------------------------------------------
    def rule_fund_recycling(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """Flags same work type at similar GPS coordinates funded across different MPs."""
        flags: Dict[str, Dict[str, Any]] = {}
        if df.empty or "latitude" not in df.columns or "longitude" not in df.columns or "mp_name" not in df.columns:
            return flags

        valid = df[df["latitude"].notnull() & df["longitude"].notnull() & (df["latitude"] != 0) & (df["longitude"] != 0)].copy()
        if len(valid) < 2:
            return flags

        group_col = "district" if "district" in valid.columns else "state"
        groups = valid.groupby(group_col) if group_col in valid.columns else [("all", valid)]

        for _, group in groups:
            records = group[["project_id", "mp_name", "work_type", "latitude", "longitude"]].to_dict("records")
            n = len(records)
            for i in range(n):
                p1 = records[i]
                for j in range(i + 1, n):
                    p2 = records[j]
                    if str(p1["mp_name"]).strip() != str(p2["mp_name"]).strip():
                        dist = haversine_meters(p1["latitude"], p1["longitude"], p2["latitude"], p2["longitude"])
                        if dist <= 200.0 and (p1["work_type"] == p2["work_type"]):
                            detail_1 = f"Same work '{p1['work_type']}' near ({p1['latitude']:.4f}, {p1['longitude']:.4f}) found in both MP {p1['mp_name']}'s and MP {p2['mp_name']}'s fund records — possible duplicate billing"
                            detail_2 = f"Same work '{p2['work_type']}' near ({p2['latitude']:.4f}, {p2['longitude']:.4f}) found in both MP {p2['mp_name']}'s and MP {p1['mp_name']}'s fund records — possible duplicate billing"

                            flags[p1["project_id"]] = {
                                "flag_name": "fund_recycling",
                                "detail": detail_1,
                                "weight": self.RULE_WEIGHTS["fund_recycling"],
                                "evidence": {"conflicting_project": p2["project_id"], "other_mp": p2["mp_name"], "distance_meters": round(dist, 1)}
                            }
                            flags[p2["project_id"]] = {
                                "flag_name": "fund_recycling",
                                "detail": detail_2,
                                "weight": self.RULE_WEIGHTS["fund_recycling"],
                                "evidence": {"conflicting_project": p1["project_id"], "other_mp": p1["mp_name"], "distance_meters": round(dist, 1)}
                            }
        return flags

    # -----------------------------------------------------------------------
    # Comprehensive Batch Analysis
    # -----------------------------------------------------------------------
    def analyze_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Executes all 8 deterministic fraud rules, aggregates triggered flags,
        and computes the cumulative red flag score (0-100) per project.
        """
        if df.empty:
            df_out = df.copy()
            df_out["flags_triggered"] = []
            df_out["flag_details"] = []
            df_out["red_flag_score"] = 0.0
            return df_out

        df_out = df.copy()

        # Run all 8 rules
        r1 = self.rule_duplicate_gps(df_out)
        r2 = self.rule_repeated_vendor(df_out)
        r3 = self.rule_cost_outlier(df_out)
        r4 = self.rule_year_end_rush(df_out)
        r5 = self.rule_phantom_completion(df_out)
        r6 = self.rule_fast_completion(df_out)
        r7 = self.rule_shell_vendor(df_out)
        r8 = self.rule_fund_recycling(df_out)

        all_rule_results = [r1, r2, r3, r4, r5, r6, r7, r8]

        flags_triggered_list: List[List[str]] = []
        flag_details_list: List[List[Dict[str, Any]]] = []
        scores_list: List[float] = []

        for _, row in df_out.iterrows():
            pid = row["project_id"]
            project_flags: List[str] = []
            project_details: List[Dict[str, Any]] = []
            total_weight = 0.0

            for rule_dict in all_rule_results:
                if pid in rule_dict:
                    info = rule_dict[pid]
                    project_flags.append(info["flag_name"])
                    project_details.append(info)
                    total_weight += info.get("weight", 0)

            # Score is the capped sum of deterministic rule weights.
            score = round(min(total_weight, 100.0), 2)

            flags_triggered_list.append(project_flags)
            flag_details_list.append(project_details)
            scores_list.append(score)

        df_out["flags_triggered"] = flags_triggered_list
        df_out["flag_details"] = flag_details_list
        df_out["red_flag_score"] = scores_list

        return df_out

    # -----------------------------------------------------------------------
    # Single-Project Legacy Adapter
    # -----------------------------------------------------------------------
    def analyze(self, project: Dict[str, Any], vendor_history: Dict[str, Any] = None) -> List[Dict]:
        """Legacy compatibility method for single-project dict inspection."""
        df_single = pd.DataFrame([project])
        df_res = self.analyze_all(df_single)
        details = df_res.iloc[0]["flag_details"]
        return [
            {
                "flag_type": d["flag_name"].upper(),
                "severity": "CRITICAL" if d["weight"] >= 30 else ("HIGH" if d["weight"] >= 20 else "MEDIUM"),
                "description": d["detail"],
                "engine_source": "RedFlagEngine",
                "evidence": d.get("evidence", {})
            }
            for d in details
        ]


# ---------------------------------------------------------------------------
# Standalone Explanation Utility
# ---------------------------------------------------------------------------
def explain_flags(flags_triggered: List[str]) -> str:
    """
    Returns a clean, formatted bullet-point explanation string suitable for UI cards.
    """
    if not flags_triggered:
        return "No red flags detected. Project parameters align with standard compliance benchmarks."

    bullets = []
    for flag in flags_triggered:
        name = flag.lower().strip()
        explanation = FLAG_EXPLANATION_TEMPLATES.get(
            name,
            f"Flag '{flag}': Anomalous behavior detected by forensic heuristic engine."
        )
        bullets.append(f"- {explanation}")

    return "\n".join(bullets)


red_flag_engine = RedFlagEngine()


# ---------------------------------------------------------------------------
# Self-Test Execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from utils.helpers import preprocess_pipeline

    sample_csv = os.path.join(_root, "data", "sample_dataset.csv")
    print(f"[*] Loading sample dataset from {sample_csv}...")
    df_preprocessed = preprocess_pipeline(sample_csv)

    print("[*] Running RedFlagEngine on all 500 records...")
    engine = RedFlagEngine()
    df_flagged = engine.analyze_all(df_preprocessed)

    flagged_count = (df_flagged["red_flag_score"] > 0).sum()
    print(f"[OK] RedFlagEngine analysis completed!")
    print(f"     - Total Projects Analyzed: {len(df_flagged)}")
    print(f"     - Projects with Red Flags Triggered: {flagged_count}")
    print(f"     - Average Red Flag Score (Flagged): {df_flagged[df_flagged['red_flag_score'] > 0]['red_flag_score'].mean():.2f}")

    # Display Top 3 Flagged Samples
    top_flagged = df_flagged.sort_values(by="red_flag_score", ascending=False).head(3)
    print("\n--- TOP FLAGGED PROJECTS DEMO ---")
    for _, r in top_flagged.iterrows():
        print(f"ID: {r['project_id']} | Score: {r['red_flag_score']} | Flags: {r['flags_triggered']}")
        print(explain_flags(r["flags_triggered"]))
        print("-" * 60)
