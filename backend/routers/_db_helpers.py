"""Shared DB serialization helpers for API routers."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from models.db_models import Flag, GeoCheckpoint, Project, ProjectStatus, RiskLevel, SurveyResponse, Vendor


def json_safe(value: Any) -> Any:
    """Convert pandas/numpy/datetime values into JSON-serializable primitives."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return value


def risk_level_value(value: Any) -> str:
    raw = str(getattr(value, "value", value) or "LOW").upper()
    return raw if raw in RiskLevel.__members__ else "LOW"


def status_value(value: Any) -> str:
    raw = str(getattr(value, "value", value) or "PROPOSED").upper()
    return raw if raw in ProjectStatus.__members__ else "PROPOSED"


def project_amount(project: Project) -> float:
    return float(project.metadata_json.get("sanctioned_amount") or project.allocated_amount or 0.0) if project.metadata_json else float(project.allocated_amount or 0.0)


def project_to_dict(project: Project, include_related: bool = False) -> Dict[str, Any]:
    metadata = project.metadata_json or {}
    data = {
        "id": project.id,
        "project_id": metadata.get("project_id", project.id),
        "title": project.title,
        "work_name": project.title,
        "work_type": metadata.get("work_type", project.title),
        "description": project.description,
        "mp_constituency": project.mp_constituency,
        "constituency": project.mp_constituency,
        "mp_name": project.mp_name,
        "state": project.state,
        "district": project.district,
        "allocated_amount": float(project.allocated_amount or 0.0),
        "sanctioned_amount": float(metadata.get("sanctioned_amount") or project.allocated_amount or 0.0),
        "disbursed_amount": float(project.disbursed_amount or 0.0),
        "expenditure": float(project.expenditure or 0.0),
        "expenditure_reported": float(metadata.get("expenditure_reported") or project.expenditure or 0.0),
        "unspent_balance": float(metadata.get("unspent_balance") or 0.0),
        "status": status_value(project.status),
        "risk_level": risk_level_value(project.risk_level),
        "risk_score": float(project.risk_score or 0.0),
        "final_risk_score": float(metadata.get("final_risk_score") or project.risk_score or 0.0),
        "red_flag_score": float(metadata.get("red_flag_score") or 0.0),
        "ml_anomaly_score": float(metadata.get("ml_anomaly_score") or 0.0),
        "nlp_risk_score": float(metadata.get("nlp_risk_score") or 0.0),
        "survey_risk_score": float(metadata.get("survey_risk_score") or 0.0),
        "latitude": project.latitude,
        "longitude": project.longitude,
        "start_date": project.start_date,
        "completion_date": project.completion_date,
        "vendor_id": project.vendor_id,
        "vendor_name": project.vendor.name if project.vendor else metadata.get("vendor_name"),
        "geo_verification_status": metadata.get("geo_verification_status", "pending"),
        "geo_status": metadata.get("geo_verification_status", "pending"),
        "flags_triggered": metadata.get("flags_triggered", []),
        "flags_count": len(project.flags) if include_related else len(metadata.get("flags_triggered", []) or []),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }
    if include_related:
        data.update({
            "flags": [flag_to_dict(flag) for flag in project.flags],
            "vendor": vendor_to_dict(project.vendor) if project.vendor else None,
            "completion_report": {
                "uc_text": metadata.get("uc_text", project.description),
                "vagueness_score": metadata.get("vagueness_score"),
                "uc_similarity_score": metadata.get("uc_similarity_score"),
                "gemini_assessment": metadata.get("gemini_assessment"),
                "gemini_flags": metadata.get("gemini_flags"),
            },
            "survey_results": [survey_to_dict(survey) for survey in project.survey_responses],
            "geo_checkpoints": [geo_to_dict(checkpoint) for checkpoint in project.geo_checkpoints],
        })
    return data


def flag_to_dict(flag: Flag) -> Dict[str, Any]:
    return {
        "id": flag.id,
        "project_id": flag.project_id,
        "vendor_id": flag.vendor_id,
        "flag_type": flag.flag_type,
        "severity": risk_level_value(flag.severity),
        "description": flag.description,
        "engine_source": flag.engine_source,
        "evidence": flag.evidence or {},
        "resolved": bool(flag.resolved),
        "created_at": flag.created_at,
    }


def survey_to_dict(survey: SurveyResponse) -> Dict[str, Any]:
    return {
        "id": survey.id,
        "project_id": survey.project_id,
        "respondent_phone": survey.respondent_phone,
        "respondent_type": survey.respondent_type,
        "work_quality_score": survey.work_quality_score,
        "work_completed": survey.work_completed,
        "bribery_reported": survey.bribery_reported,
        "comments": survey.comments,
        "sentiment_score": survey.sentiment_score,
        "survey_date": survey.survey_date,
    }


def geo_to_dict(checkpoint: GeoCheckpoint) -> Dict[str, Any]:
    return {
        "id": checkpoint.id,
        "project_id": checkpoint.project_id,
        "check_type": checkpoint.check_type,
        "latitude": checkpoint.latitude,
        "longitude": checkpoint.longitude,
        "osm_data": checkpoint.osm_data or {},
        "satellite_verified": checkpoint.satellite_verified,
        "anomaly_detected": checkpoint.anomaly_detected,
        "notes": checkpoint.notes,
        "checked_at": checkpoint.checked_at,
    }


def vendor_to_dict(vendor: Optional[Vendor], include_projects: bool = False) -> Optional[Dict[str, Any]]:
    if vendor is None:
        return None
    data = {
        "id": vendor.id,
        "name": vendor.name,
        "registration_number": vendor.registration_number,
        "pan_number": vendor.pan_number,
        "address": vendor.address,
        "contact_email": vendor.contact_email,
        "contact_phone": vendor.contact_phone,
        "blacklisted": bool(vendor.blacklisted),
        "risk_score": float(vendor.risk_score or 0.0),
        "total_contracts": int(vendor.total_contracts or 0),
        "total_contract_value": float(vendor.total_contract_value or 0.0),
        "cluster_id": None,
        "collusion_suspected": bool(vendor.metadata_json.get("collusion_suspected")) if hasattr(vendor, "metadata_json") and vendor.metadata_json else False,
        "created_at": vendor.created_at,
        "updated_at": vendor.updated_at,
    }
    if include_projects:
        data["projects"] = [project_to_dict(project) for project in vendor.projects]
    return data


def projects_to_dataframe(projects: Iterable[Project]) -> pd.DataFrame:
    rows = [project_to_dict(project) for project in projects]
    return pd.DataFrame(rows)


def get_or_create_vendor(db: Session, row: pd.Series) -> Optional[Vendor]:
    name = row.get("vendor_name")
    if pd.isna(name) or not str(name).strip():
        return None

    name = str(name).strip()
    reg = row.get("vendor_reg_no")
    pan = row.get("vendor_pan")
    query = db.query(Vendor)
    vendor = None
    if pd.notna(reg) and str(reg).strip():
        vendor = query.filter(Vendor.registration_number == str(reg).strip()).first()
    if vendor is None and pd.notna(pan) and str(pan).strip():
        vendor = query.filter(Vendor.pan_number == str(pan).strip()).first()
    if vendor is None:
        vendor = query.filter(Vendor.name == name).first()
    if vendor is None:
        vendor = Vendor(
            name=name,
            registration_number=str(reg).strip() if pd.notna(reg) and str(reg).strip() else None,
            pan_number=str(pan).strip() if pd.notna(pan) and str(pan).strip() else None,
        )
        db.add(vendor)
        db.flush()
    return vendor


def store_scored_dataframe(db: Session, df: pd.DataFrame, replace_existing: bool = True) -> int:
    """Persist scored projects, vendors, and flag details to the database."""
    if replace_existing:
        db.query(GeoCheckpoint).delete()
        db.query(SurveyResponse).delete()
        db.query(Flag).delete()
        db.query(Project).delete()
        db.commit()

    created = 0
    for _, row in df.iterrows():
        vendor = get_or_create_vendor(db, row)
        metadata = {str(column): json_safe(row[column]) for column in df.columns}
        status = status_value(row.get("status"))
        risk_level = risk_level_value(row.get("risk_level"))
        project = Project(
            title=str(row.get("title") or row.get("work_type") or row.get("project_id") or "Untitled Project"),
            description=str(row.get("uc_text") or row.get("description") or ""),
            mp_constituency=str(row.get("constituency") or row.get("mp_constituency") or ""),
            mp_name=str(row.get("mp_name") or ""),
            state=str(row.get("state") or ""),
            district=str(row.get("district") or ""),
            allocated_amount=float(row.get("allocated_amount") or row.get("sanctioned_amount") or 0.0),
            disbursed_amount=float(row.get("expenditure_reported") or row.get("disbursed_amount") or 0.0),
            expenditure=float(row.get("expenditure_reported") or row.get("expenditure") or 0.0),
            status=ProjectStatus[status],
            risk_level=RiskLevel[risk_level],
            risk_score=float(row.get("final_risk_score") or row.get("risk_score") or 0.0),
            latitude=float(row["latitude"]) if pd.notna(row.get("latitude")) else None,
            longitude=float(row["longitude"]) if pd.notna(row.get("longitude")) else None,
            start_date=row.get("sanction_date") if pd.notna(row.get("sanction_date")) else None,
            completion_date=row.get("completion_date") if pd.notna(row.get("completion_date")) else None,
            vendor_id=vendor.id if vendor else None,
            metadata_json=metadata,
        )
        db.add(project)
        db.flush()

        for detail in row.get("flag_details", []) or []:
            flag_name = detail.get("flag_name", "UNKNOWN")
            weight = float(detail.get("weight", 0) or 0)
            severity = "CRITICAL" if weight >= 35 else "HIGH" if weight >= 25 else "MEDIUM" if weight >= 15 else "LOW"
            db.add(Flag(
                project_id=project.id,
                vendor_id=vendor.id if vendor else None,
                flag_type=str(flag_name).upper(),
                severity=RiskLevel[severity],
                description=str(detail.get("detail") or flag_name),
                engine_source="RedFlagEngine",
                evidence=json_safe(detail.get("evidence") or {}),
            ))
        created += 1

    refresh_vendor_rollups(db)
    db.commit()
    return created


def refresh_vendor_rollups(db: Session) -> None:
    for vendor in db.query(Vendor).all():
        projects = vendor.projects
        vendor.total_contracts = len(projects)
        vendor.total_contract_value = round(sum(project_amount(project) for project in projects), 2)
        vendor.risk_score = round(sum(float(project.risk_score or 0.0) for project in projects) / len(projects), 2) if projects else 0.0
