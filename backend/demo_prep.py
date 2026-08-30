"""Prepare MPLAD FraudShield demo data and verify critical fraud signals."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from database import Base, SessionLocal, engine
from engines.risk_aggregator import RiskAggregator
from models import db_models  # noqa: F401 - ensures SQLAlchemy models are registered
from routers._db_helpers import store_scored_dataframe
from utils.helpers import generate_sample_mplad_dataset, preprocess_pipeline


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("[1/5] Resetting database...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    print("[2/5] Generating sample dataset with known fraud patterns...")
    data_dir = BACKEND_ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    sample_path = data_dir / "sample_dataset.csv"
    generate_sample_mplad_dataset(500).to_csv(sample_path, index=False, encoding="utf-8")

    print("[3/5] Running full analysis pipeline...")
    df = preprocess_pipeline(str(sample_path))
    scored = RiskAggregator().run_full_analysis(df)

    critical = scored[scored["risk_level"] == "CRITICAL"].sort_values("final_risk_score", ascending=False)
    if critical.empty:
        raise RuntimeError("Demo verification failed: no CRITICAL projects were detected.")

    print("[4/5] Persisting analyzed projects, vendors, and flags...")
    db = SessionLocal()
    try:
        records = store_scored_dataframe(db, scored, replace_existing=True)
    finally:
        db.close()

    print("[5/5] Verifying demo report...")
    print("\n========== MPLAD FraudShield Demo Ready ==========")
    print(f"Total projects: {records}")
    print(f"Critical projects: {len(critical)}")
    print("\nTop 3 flagged projects:")
    for _, row in critical.head(3).iterrows():
        flags = row.get("flags_triggered", [])
        flag_text = ", ".join(flags) if isinstance(flags, list) and flags else "No named flags"
        print(f"- {row.get('project_id')} | {row.get('work_type')} | Score {row.get('final_risk_score')} | {flag_text}")

    print("\n✅ Demo ready. Open http://localhost:8000/docs to see the API")


if __name__ == "__main__":
    main()
