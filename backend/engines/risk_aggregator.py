"""
Risk aggregation for MPLAD FraudShield.

Combines deterministic red flags, ML anomaly scores, NLP UC risk, and citizen
survey signals into a final project-level risk score.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

_curr = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_curr, ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from engines.red_flag_engine import RedFlagEngine
    from engines.ml_engine import MLAnomalyEngine
    from engines.nlp_engine import NLPRiskEngine
except ImportError:  # pragma: no cover - package import fallback
    from backend.engines.red_flag_engine import RedFlagEngine
    from backend.engines.ml_engine import MLAnomalyEngine
    from backend.engines.nlp_engine import NLPRiskEngine

logger = logging.getLogger(__name__)


SEVERITY_WEIGHTS = {
    "LOW": 5,
    "MEDIUM": 15,
    "HIGH": 30,
    "CRITICAL": 50,
}


def classify_risk(score: float) -> str:
    """Backward-compatible risk classifier for legacy single-project callers."""
    return RiskAggregator.risk_level_for_score(score)


class RiskAggregator:
    """Aggregates all engine outputs into project, MP, and dashboard risk views."""

    WEIGHTS = {
        "red_flag": 0.40,
        "ml_anomaly": 0.35,
        "nlp_risk": 0.25,
    }

    RISK_THRESHOLDS = {
        "CRITICAL": 75,
        "HIGH": 50,
        "MEDIUM": 30,
        "LOW": 0,
    }

    SCORE_COLUMNS = {
        "red_flag": "red_flag_score",
        "ml_anomaly": "ml_anomaly_score",
        "nlp_risk": "nlp_risk_score",
    }

    AMOUNT_COLUMNS = (
        "sanctioned_amount",
        "allocated_amount",
        "contract_amount",
        "expenditure_reported",
    )

    def __init__(
        self,
        red_flag_engine: Optional[RedFlagEngine] = None,
        ml_engine: Optional[MLAnomalyEngine] = None,
        nlp_engine: Optional[NLPRiskEngine] = None,
    ) -> None:
        self.red_flag_engine = red_flag_engine or RedFlagEngine()
        self.ml_engine = ml_engine or MLAnomalyEngine()
        self.nlp_engine = nlp_engine or NLPRiskEngine()

    @classmethod
    def risk_level_for_score(cls, score: Any) -> str:
        """Map a numeric score to CRITICAL/HIGH/MEDIUM/LOW thresholds."""
        try:
            value = float(score)
        except (TypeError, ValueError):
            value = 0.0

        for level, threshold in sorted(cls.RISK_THRESHOLDS.items(), key=lambda item: item[1], reverse=True):
            if value >= threshold:
                return level
        return "LOW"

    @staticmethod
    def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
        if column not in df.columns:
            return pd.Series(0.0, index=df.index, dtype=float)
        return pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    @classmethod
    def _amount_column(cls, df: pd.DataFrame) -> Optional[str]:
        for column in cls.AMOUNT_COLUMNS:
            if column in df.columns:
                return column
        return None

    @staticmethod
    def _safe_scalar(value: Any, default: Any = "") -> Any:
        if pd.isna(value):
            return default
        if isinstance(value, np.generic):
            return value.item()
        return value

    def compute_final_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute final_risk_score and risk_level for each project.

        Missing component scores are treated as zero. Survey risk contributes an
        additive bonus capped at 30 points, and final scores are clamped to 0-100.
        """
        result = df.copy()

        weighted_score = pd.Series(0.0, index=result.index, dtype=float)
        for weight_key, column in self.SCORE_COLUMNS.items():
            weighted_score += self._numeric_series(result, column) * self.WEIGHTS[weight_key]

        survey_bonus = self._numeric_series(result, "survey_risk_score").clip(lower=0.0, upper=30.0)
        deterministic_floor = self._numeric_series(result, "red_flag_score")
        if "flags_triggered" in result.columns:
            multi_flag_bonus = result["flags_triggered"].apply(
                lambda flags: min(max(len(flags) - 1, 0) * 8, 24) if isinstance(flags, list) else 0
            )
            deterministic_floor = deterministic_floor + multi_flag_bonus

        final_score = pd.concat([
            weighted_score + survey_bonus,
            deterministic_floor,
        ], axis=1).max(axis=1).clip(lower=0.0, upper=100.0).round(2)

        result["final_risk_score"] = final_score
        result["risk_score"] = final_score
        result["risk_level"] = final_score.apply(self.risk_level_for_score)
        return result

    def get_mp_risk_profile(self, df: pd.DataFrame, mp_name: str) -> Dict[str, Any]:
        """Return a detailed risk profile for one MP."""
        scored = df if {"final_risk_score", "risk_level"}.issubset(df.columns) else self.compute_final_scores(df)
        if "mp_name" not in scored.columns:
            mp_df = scored.iloc[0:0].copy()
        else:
            mp_df = scored[scored["mp_name"].fillna("").astype(str).str.casefold() == str(mp_name).casefold()].copy()

        if mp_df.empty:
            return {
                "mp_name": mp_name,
                "constituency": "",
                "state": "",
                "total_projects": 0,
                "critical_count": 0,
                "high_count": 0,
                "avg_risk_score": 0.0,
                "total_funds_at_risk": 0.0,
                "top_flags": [],
                "projects": [],
            }

        amount_col = self._amount_column(mp_df)
        at_risk_mask = mp_df["risk_level"].isin(["HIGH", "CRITICAL"])
        amount_series = self._numeric_series(mp_df, amount_col) if amount_col else pd.Series(0.0, index=mp_df.index)

        flags: List[str] = []
        if "flags_triggered" in mp_df.columns:
            for item in mp_df["flags_triggered"]:
                if isinstance(item, (list, tuple, set)):
                    flags.extend(str(flag) for flag in item if pd.notna(flag))
                elif pd.notna(item) and str(item).strip():
                    flags.extend(part.strip() for part in str(item).split(",") if part.strip())

        sorted_projects = mp_df.sort_values("final_risk_score", ascending=False)
        projects = [self._project_summary(row, amount_col) for _, row in sorted_projects.iterrows()]

        first_row = mp_df.iloc[0]
        return {
            "mp_name": str(self._safe_scalar(first_row.get("mp_name"), mp_name)),
            "constituency": str(self._safe_scalar(first_row.get("constituency"), "")),
            "state": str(self._safe_scalar(first_row.get("state"), "")),
            "total_projects": int(len(mp_df)),
            "critical_count": int((mp_df["risk_level"] == "CRITICAL").sum()),
            "high_count": int((mp_df["risk_level"] == "HIGH").sum()),
            "avg_risk_score": round(float(mp_df["final_risk_score"].mean()), 2),
            "total_funds_at_risk": round(float(amount_series[at_risk_mask].sum()), 2),
            "top_flags": [flag for flag, _ in Counter(flags).most_common(3)],
            "projects": projects,
        }

    def get_dashboard_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Return dashboard aggregate metrics for a scored or unscored DataFrame."""
        scored = df if {"final_risk_score", "risk_level"}.issubset(df.columns) else self.compute_final_scores(df)
        amount_col = self._amount_column(scored)
        amounts = self._numeric_series(scored, amount_col) if amount_col else pd.Series(0.0, index=scored.index)
        at_risk_mask = scored["risk_level"].isin(["HIGH", "CRITICAL"])

        risk_distribution = {
            level: int((scored["risk_level"] == level).sum())
            for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        }

        top_risky_mps: List[Dict[str, Any]] = []
        if "mp_name" in scored.columns and not scored.empty:
            grouped = scored.groupby("mp_name", dropna=False).agg(
                avg_risk_score=("final_risk_score", "mean"),
                total_projects=("final_risk_score", "size"),
            ).reset_index()
            grouped = grouped.sort_values("avg_risk_score", ascending=False).head(10)
            top_risky_mps = [
                {
                    "mp_name": str(self._safe_scalar(row["mp_name"], "Unknown")),
                    "avg_risk_score": round(float(row["avg_risk_score"]), 2),
                    "total_projects": int(row["total_projects"]),
                }
                for _, row in grouped.iterrows()
            ]

        state_risk_summary = {}
        if "state" in scored.columns and not scored.empty:
            state_risk_summary = {
                str(self._safe_scalar(state, "Unknown")): round(float(score), 2)
                for state, score in scored.groupby("state", dropna=False)["final_risk_score"].mean().items()
            }

        work_type_distribution = {}
        if "work_type" in scored.columns:
            work_type_distribution = {
                str(self._safe_scalar(work_type, "Unknown")): int(count)
                for work_type, count in scored["work_type"].fillna("Unknown").value_counts().items()
            }

        return {
            "total_projects": int(len(scored)),
            "critical_count": risk_distribution["CRITICAL"],
            "high_count": risk_distribution["HIGH"],
            "medium_count": risk_distribution["MEDIUM"],
            "low_count": risk_distribution["LOW"],
            "total_funds_analyzed": round(float(amounts.sum()), 2),
            "funds_at_risk": round(float(amounts[at_risk_mask].sum()), 2),
            "avg_risk_score": round(float(scored["final_risk_score"].mean()) if not scored.empty else 0.0, 2),
            "top_risky_mps": top_risky_mps,
            "state_risk_summary": state_risk_summary,
            "work_type_distribution": work_type_distribution,
            "risk_distribution": risk_distribution,
        }

    def run_full_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Run RedFlagEngine -> MLAnomalyEngine -> NLPRiskEngine -> final scoring.

        This is the main post-ingestion entry point for full DataFrame scoring.
        Timing for each stage is logged at INFO level.
        """
        stages = [
            ("RedFlagEngine", self.red_flag_engine.analyze_all),
            ("MLAnomalyEngine", self.ml_engine.score),
            ("NLPRiskEngine", self.nlp_engine.analyze_project_texts),
            ("RiskAggregator.compute_final_scores", self.compute_final_scores),
        ]

        result = df.copy()
        total_start = time.perf_counter()
        for name, func in stages:
            stage_start = time.perf_counter()
            result = func(result)
            elapsed = time.perf_counter() - stage_start
            logger.info("%s completed in %.3fs for %d records", name, elapsed, len(result))

        logger.info("Full risk analysis completed in %.3fs for %d records", time.perf_counter() - total_start, len(result))
        return result

    def aggregate(self, all_flags: List[Dict[str, Any]], nlp_boost: float = 0.0) -> Dict[str, Any]:
        """
        Legacy single-project adapter.

        Args:
            all_flags: Combined list of flag dicts from all engines.
            nlp_boost: Extra risk from NLP engine in the old 0.0-0.5 style.
        """
        base_score = sum(SEVERITY_WEIGHTS.get(str(f.get("severity", "LOW")).upper(), 5) for f in all_flags)
        risk_score = min(base_score + (float(nlp_boost or 0.0) * 100.0), 100.0)

        flag_summary: Dict[str, int] = {}
        for flag in all_flags:
            flag_type = str(flag.get("flag_type") or flag.get("flag_name") or "UNKNOWN")
            flag_summary[flag_type] = flag_summary.get(flag_type, 0) + 1

        return {
            "risk_score": round(risk_score, 2),
            "final_risk_score": round(risk_score, 2),
            "risk_level": self.risk_level_for_score(risk_score),
            "flag_summary": flag_summary,
            "total_flags": len(all_flags),
        }

    def _project_summary(self, row: pd.Series, amount_col: Optional[str]) -> Dict[str, Any]:
        amount = row.get(amount_col, 0.0) if amount_col else 0.0
        try:
            amount_value = round(float(amount), 2)
        except (TypeError, ValueError):
            amount_value = 0.0

        return {
            "project_id": self._safe_scalar(row.get("project_id"), ""),
            "title": str(self._safe_scalar(row.get("title", row.get("work_type")), "")),
            "work_type": str(self._safe_scalar(row.get("work_type"), "")),
            "district": str(self._safe_scalar(row.get("district"), "")),
            "amount": amount_value,
            "risk_score": round(float(row.get("final_risk_score", 0.0) or 0.0), 2),
            "risk_level": str(self._safe_scalar(row.get("risk_level"), "LOW")),
            "flags_triggered": row.get("flags_triggered", []) if isinstance(row.get("flags_triggered", []), list) else [],
        }


risk_aggregator = RiskAggregator()
