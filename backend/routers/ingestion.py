"""Ingestion router - bulk import of project data from CSV/JSON."""
import io
import logging
from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import Project, Vendor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/csv/projects")
async def ingest_projects_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Ingest project data from a CSV file."""
    try:
        import pandas as pd
        content = await file.read()
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))

        required_cols = {"title", "allocated_amount"}
        missing = required_cols - set(df.columns)
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing columns: {missing}")

        errors = []
        created = 0
        for _, row in df.iterrows():
            try:
                project = Project(
                    title=str(row.get("title", "")),
                    description=str(row.get("description", "")),
                    mp_constituency=str(row.get("mp_constituency", "")),
                    mp_name=str(row.get("mp_name", "")),
                    state=str(row.get("state", "")),
                    district=str(row.get("district", "")),
                    allocated_amount=float(row.get("allocated_amount", 0)),
                    disbursed_amount=float(row.get("disbursed_amount", 0)),
                    expenditure=float(row.get("expenditure", 0)),
                )
                db.add(project)
                created += 1
            except Exception as e:
                errors.append(str(e))

        db.commit()
        return {"message": "Import complete", "records_processed": created, "errors": errors}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed/demo")
def seed_demo_data(db: Session = Depends(get_db)):
    """Seed the database with benchmark demo data."""
    from utils.benchmark_data import generate_sample_vendors, generate_sample_projects

    # Seed vendors
    vendor_objs = []
    for v in generate_sample_vendors(20):
        vendor = Vendor(**v)
        db.add(vendor)
        vendor_objs.append(vendor)
    db.flush()

    # Seed projects (assign random vendors)
    import random
    for p in generate_sample_projects(50):
        start_date = p.pop("start_date", None)
        project = Project(**p)
        if vendor_objs:
            project.vendor_id = random.choice(vendor_objs).id
        db.add(project)

    db.commit()
    return {"message": "Demo data seeded successfully", "vendors": 20, "projects": 50}


@router.post("/use-sample")
def use_sample_data(db: Session = Depends(get_db)):
    """Load the canonical sample dataset, run risk analysis, and persist it."""
    from pathlib import Path
    from engines.risk_aggregator import RiskAggregator
    from routers._db_helpers import store_scored_dataframe
    from utils.helpers import generate_sample_mplad_dataset, preprocess_pipeline

    data_dir = Path(__file__).resolve().parents[1] / "data"
    data_dir.mkdir(exist_ok=True)
    sample_path = data_dir / "sample_dataset.csv"

    if not sample_path.exists():
        generate_sample_mplad_dataset(500).to_csv(sample_path, index=False, encoding="utf-8")

    df = preprocess_pipeline(str(sample_path))
    scored = RiskAggregator().run_full_analysis(df)
    records_processed = store_scored_dataframe(db, scored, replace_existing=True)
    critical_count = int((scored["risk_level"] == "CRITICAL").sum())

    return {
        "message": "Sample dataset analyzed and loaded successfully",
        "records_processed": records_processed,
        "projects_ingested": records_processed,
        "critical_count": critical_count,
        "errors": [],
    }
