"""Citizen survey endpoints for dispatch, public forms, and results."""
from __future__ import annotations

import os
from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from engines.nlp_engine import nlp_engine
from models.db_models import Project, SurveyBatch, SurveyResponse
from schemas.pydantic_schemas import (
    CitizenSurveyPublicLink,
    CitizenSurveyResults,
    CitizenSurveySubmit,
    CitizenSurveyThankYou,
    SurveyDispatchResponse,
    SurveyResponseRead,
)
from tasks.survey_dispatcher import dispatch_project_survey, survey_dispatcher

router = APIRouter()


def _find_project(db: Session, project_id: str) -> Optional[Project]:
    try:
        project = db.query(Project).filter(Project.id == int(project_id)).first()
        if project:
            return project
    except (TypeError, ValueError):
        pass

    for project in db.query(Project).all():
        if str((project.metadata_json or {}).get("project_id", "")) == str(project_id):
            return project
    return None


def _public_project_id(project: Project) -> str:
    return str((project.metadata_json or {}).get("project_id") or project.id)


def _amount_lakhs(project: Project) -> float:
    metadata = project.metadata_json or {}
    return round(float(metadata.get("sanctioned_amount") or project.allocated_amount or 0.0), 2)


@router.post("/trigger/{project_id}", response_model=SurveyDispatchResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_survey(project_id: str, db: Session = Depends(get_db)):
    """Manually trigger citizen survey dispatch for a project."""
    project = _find_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    public_id = _public_project_id(project)
    if dispatch_project_survey is not None:
        try:
            task = dispatch_project_survey.delay(
                public_id,
                project.title,
                project.mp_name or "",
                project.district or "",
                project.state or "",
            )
            phones = survey_dispatcher._phones_for_location(project.district or "")
            return {"batch_id": str(task.id), "phones_queued": len(phones), "project_id": public_id}
        except Exception:
            pass

    result = survey_dispatcher.dispatch_survey(
        public_id,
        project.title,
        project.mp_name or "",
        project.district or "",
        project.state or "",
    )
    return {"batch_id": result["batch_id"], "phones_queued": int(result["phones_queued"]), "project_id": public_id}


@router.get("/{project_id}/results", response_model=CitizenSurveyResults)
def get_survey_results(project_id: str, db: Session = Depends(get_db)):
    """Return aggregated citizen survey results for a project."""
    project = _find_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    responses = db.query(SurveyResponse).filter(SurveyResponse.project_id == project.id).all()
    batches = db.query(SurveyBatch).filter(SurveyBatch.project_id == project.id).all()
    sent_count = sum(batch.sent_count or 0 for batch in batches)
    response_count = len(responses)
    response_rate = round((response_count / sent_count * 100.0) if sent_count else 0.0, 2)

    satisfaction_values = [
        response.satisfaction_score if response.satisfaction_score is not None else response.work_quality_score
        for response in responses
        if response.satisfaction_score is not None or response.work_quality_score is not None
    ]
    avg_satisfaction = round(sum(satisfaction_values) / len(satisfaction_values), 2) if satisfaction_values else 0.0
    aware_count = sum(1 for response in responses if response.work_completed is True)
    aware_citizens_pct = round((aware_count / response_count * 100.0) if response_count else 0.0, 2)
    common_issues = _common_issues(responses)

    return {
        "sent_count": int(sent_count),
        "response_count": response_count,
        "response_rate": response_rate,
        "avg_satisfaction": avg_satisfaction,
        "aware_citizens_pct": aware_citizens_pct,
        "common_issues": common_issues,
        "all_responses": [_survey_response_item(response) for response in responses],
    }


@router.post("/{survey_id}/respond", response_model=CitizenSurveyThankYou, status_code=status.HTTP_201_CREATED)
def submit_citizen_response(survey_id: str, payload: CitizenSurveySubmit, db: Session = Depends(get_db)):
    """Record a citizen survey response from the public SMS form."""
    project = _find_project(db, survey_id)
    if not project:
        raise HTTPException(status_code=404, detail="Survey/project not found")

    nlp_result = nlp_engine.analyze_survey_comment(payload.comments or "")
    survey = SurveyResponse(
        project_id=project.id,
        respondent_type="citizen",
        work_quality_score=payload.quality_score,
        work_completed=payload.saw_project,
        satisfaction_score=payload.satisfaction_score,
        money_spent_properly=payload.money_spent_properly,
        bribery_reported=payload.money_spent_properly == "no",
        comments=payload.comments,
        sentiment_score=float(nlp_result.get("sentiment_score", 0.0)),
    )
    db.add(survey)
    db.commit()
    survey_dispatcher.update_risk_from_surveys(_public_project_id(project))
    return {"thank_you": "Your response has been recorded. 🇮🇳"}


@router.get("/link/{project_id}", response_model=CitizenSurveyPublicLink)
def get_survey_link(project_id: str, db: Session = Depends(get_db)):
    """Return public survey form data for citizens opening an SMS link."""
    project = _find_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    public_id = _public_project_id(project)
    frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
    return {
        "project_id": public_id,
        "work_name": project.title,
        "mp_name": project.mp_name,
        "district": project.district,
        "state": project.state,
        "amount": _amount_lakhs(project),
        "survey_url": f"{frontend_base_url}/survey/{public_id}",
    }


@router.get("/", response_model=List[SurveyResponseRead])
def list_surveys(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List raw survey responses for admin/debug views."""
    return db.query(SurveyResponse).offset(skip).limit(limit).all()


@router.get("/project/{project_id}", response_model=List[SurveyResponseRead])
def get_surveys_for_project(project_id: int, db: Session = Depends(get_db)):
    """Return raw survey responses for a numeric database project ID."""
    return db.query(SurveyResponse).filter(SurveyResponse.project_id == project_id).all()


def _survey_response_item(response: SurveyResponse) -> dict:
    return {
        "id": response.id,
        "saw_project": response.work_completed,
        "quality_score": response.work_quality_score,
        "satisfaction_score": response.satisfaction_score,
        "money_spent_properly": response.money_spent_properly,
        "comments": response.comments,
        "sentiment_score": response.sentiment_score,
        "survey_date": response.survey_date,
    }


def _common_issues(responses: List[SurveyResponse]) -> List[str]:
    issues: List[str] = []
    for response in responses:
        if response.work_completed is False:
            issues.append("project_not_seen")
        if response.work_quality_score is not None and response.work_quality_score <= 2:
            issues.append("poor_quality")
        if response.satisfaction_score is not None and response.satisfaction_score <= 2:
            issues.append("low_satisfaction")
        if response.money_spent_properly == "no":
            issues.append("fund_misuse_concern")
        if response.comments:
            text = response.comments.lower()
            for keyword in ["delay", "poor", "incomplete", "fraud", "bribe", "missing", "broken"]:
                if keyword in text:
                    issues.append(keyword)
    return [issue for issue, _ in Counter(issues).most_common(10)]
