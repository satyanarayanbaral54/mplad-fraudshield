"""
Batch Analysis Task - Celery task to run all engines on all projects.
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def run_full_analysis_on_project(project: Dict[str, Any], vendor: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Run all engines on a single project and return aggregated results.
    This is designed to be called from a Celery task or directly.
    """
    from engines.red_flag_engine import red_flag_engine
    from engines.ml_engine import ml_engine
    from engines.nlp_engine import nlp_engine
    from engines.risk_aggregator import risk_aggregator

    all_flags = []

    # 1. Rule-based flags
    rule_flags = red_flag_engine.analyze(project, vendor)
    all_flags.extend(rule_flags)

    # 2. ML anomaly detection
    ml_result = ml_engine.predict(project)
    all_flags.extend(ml_result.get("flags", []))

    # 3. NLP analysis
    nlp_result = nlp_engine.analyze_description(project.get("description", ""))
    all_flags.extend(nlp_result.get("flags", []))

    # 4. Aggregate
    aggregated = risk_aggregator.aggregate(all_flags, nlp_result.get("risk_boost", 0.0))

    return {
        "project_id": project.get("id"),
        "flags": all_flags,
        **aggregated,
    }


try:
    from celery import Celery
    from config import settings

    celery_app = Celery("mplad_tasks", broker=settings.redis_url, backend=settings.redis_url)

    @celery_app.task(name="batch_analysis.analyze_all_projects")
    def analyze_all_projects():
        """Celery task: run fraud analysis on all projects in DB."""
        logger.info("Starting batch analysis of all projects...")
        # Import here to avoid circular imports at module load
        from database import SessionLocal
        from models.db_models import Project, Vendor, Flag
        from schemas.pydantic_schemas import FlagCreate

        db = SessionLocal()
        try:
            projects = db.query(Project).all()
            processed = 0
            for p in projects:
                p_dict = {
                    "id": p.id, "title": p.title, "description": p.description,
                    "allocated_amount": p.allocated_amount,
                    "disbursed_amount": p.disbursed_amount,
                    "expenditure": p.expenditure,
                    "status": p.status.value if p.status else "PROPOSED",
                }
                vendor_dict = None
                if p.vendor:
                    vendor_dict = {"id": p.vendor.id, "blacklisted": p.vendor.blacklisted,
                                   "total_contracts": p.vendor.total_contracts}

                result = run_full_analysis_on_project(p_dict, vendor_dict)

                # Update risk score on project
                p.risk_score = result["risk_score"]
                p.risk_level = result["risk_level"]

                # Save new flags (skip duplicates)
                for flag in result["flags"]:
                    db_flag = Flag(
                        project_id=p.id,
                        flag_type=flag["flag_type"],
                        severity=flag["severity"],
                        description=flag["description"],
                        engine_source=flag.get("engine_source"),
                        evidence=flag.get("evidence"),
                    )
                    db.add(db_flag)

                processed += 1

            db.commit()
            logger.info(f"Batch analysis complete. Processed {processed} projects.")
            return {"processed": processed}
        except Exception as e:
            db.rollback()
            logger.error(f"Batch analysis failed: {e}")
            raise
        finally:
            db.close()

except ImportError:
    logger.warning("Celery not available; batch tasks disabled.")
    celery_app = None
