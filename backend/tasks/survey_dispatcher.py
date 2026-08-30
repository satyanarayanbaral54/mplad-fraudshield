"""Citizen survey SMS dispatcher for MPLAD FraudShield."""
from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import Any, Dict, List, Optional

import httpx

from database import SessionLocal
from models.db_models import Project, RiskLevel, SurveyBatch

logger = logging.getLogger(__name__)


class SurveyDispatcher:
    """Dispatch citizen survey links via MSG91 or simulated SMS for demos."""

    DEMO_PHONES = {
        "default": [
            "+919876543210",
            "+919812345678",
            "+917890123456",
            "+916789012345",
            "+915678901234",
        ],
        "Prayagraj": ["+919876543210", "+919812345678", "+917890123456", "+916789012345", "+915678901234"],
        "Bengaluru Urban": ["+919900001111", "+919900002222", "+919900003333", "+919900004444", "+919900005555"],
    }

    SMS_TEMPLATE = (
        "🏗️ MPLAD Citizen Survey | एक सरकारी परियोजना आपके क्षेत्र में पूरी हुई है: "
        "Work: {work_name} | Location: {district}, {state} Amount: ₹{amount} Lakhs "
        "Rate this project: {survey_url} आपकी राय भ्रष्टाचार रोकेगी 🇮🇳 — MPLAD FraudShield"
    )

    def __init__(self, msg91_api_key: Optional[str] = None, sender_id: Optional[str] = None) -> None:
        self.msg91_api_key = msg91_api_key or os.getenv("MSG91_API_KEY", "")
        self.msg91_flow_id = os.getenv("MSG91_FLOW_ID", "")
        self.sender_id = sender_id or os.getenv("MSG91_SENDER_ID", "MPLADS")
        self.frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")

    def dispatch_survey(
        self,
        project_id: str,
        project_name: str,
        mp_name: str,
        district: str,
        state: str,
    ) -> Dict[str, Any]:
        """Send or simulate survey SMS messages and log a SurveyBatch row."""
        db = SessionLocal()
        try:
            project = self._find_project(db, project_id)
            amount = 0.0
            if project is not None:
                metadata = project.metadata_json or {}
                amount = float(metadata.get("sanctioned_amount") or project.allocated_amount or 0.0)

            phones = self._phones_for_location(district)
            survey_url = f"{self.frontend_base_url}/survey/{project_id}"
            message = self.SMS_TEMPLATE.format(
                work_name=project_name,
                district=district,
                state=state,
                amount=round(amount, 2),
                survey_url=survey_url,
            )

            provider = "MSG91" if self.msg91_api_key and self.msg91_flow_id else "SIMULATED"
            sent = 0
            failed = 0
            for phone in phones:
                ok = self.send_msg91_sms(phone, message) if provider == "MSG91" else self.send_simulated_sms(phone, message)
                sent += int(ok)
                failed += int(not ok)

            batch_id = f"survey-{uuid.uuid4().hex[:12]}"
            if project is not None:
                db.add(SurveyBatch(
                    batch_id=batch_id,
                    project_id=project.id,
                    provider=provider,
                    phones_queued=len(phones),
                    sent_count=sent,
                    failed_count=failed,
                    message=message,
                    phones=phones,
                ))
                db.commit()

            return {
                "batch_id": batch_id,
                "sent": sent,
                "failed": failed,
                "phones_queued": len(phones),
                "provider": provider,
                "survey_url": survey_url,
            }
        finally:
            db.close()

    def send_msg91_sms(self, phone: str, message: str) -> bool:
        """Send one SMS via MSG91 flow API."""
        if not self.msg91_api_key or not self.msg91_flow_id:
            return False

        payload = {
            "template_id": self.msg91_flow_id,
            "sender": self.sender_id,
            "short_url": "0",
            "recipients": [{"mobiles": phone.lstrip("+"), "message": message}],
        }
        headers = {"authkey": self.msg91_api_key, "Content-Type": "application/json"}
        try:
            response = httpx.post("https://api.msg91.com/api/v5/flow/", json=payload, headers=headers, timeout=15)
            return response.status_code == 200
        except httpx.HTTPError as exc:
            logger.warning("MSG91 SMS failed for %s: %s", phone, exc)
            return False

    def send_simulated_sms(self, phone: str, message: str) -> bool:
        """Log demo SMS output when MSG91 credentials are unavailable."""
        line = f"[SIMULATED SMS] To: {phone} | Message: {message[:100]}..."
        encoding = sys.stdout.encoding or "utf-8"
        print(line.encode(encoding, errors="replace").decode(encoding, errors="replace"))
        logger.info("[SIMULATED SMS] To: %s | Message: %s...", phone, message[:100])
        return True

    def update_risk_from_surveys(self, project_id: str) -> float:
        """Compute survey risk and update the project's final risk score metadata."""
        db = SessionLocal()
        try:
            project = self._find_project(db, project_id)
            if project is None:
                raise ValueError(f"Project not found: {project_id}")

            responses = project.survey_responses
            sent_count = sum(batch.sent_count or 0 for batch in db.query(SurveyBatch).filter(SurveyBatch.project_id == project.id).all())
            response_count = len(responses)
            aware_count = sum(1 for response in responses if response.work_completed is True)
            avg_satisfaction = (
                sum((response.satisfaction_score or response.work_quality_score or 0) for response in responses) / response_count
                if response_count else 0.0
            )
            awareness_rate = aware_count / response_count if response_count else 0.0
            response_rate = response_count / sent_count if sent_count else 0.0

            survey_risk_score = 0.0
            if response_count:
                survey_risk_score += max(0.0, (1.0 - awareness_rate) * 15.0)
                survey_risk_score += max(0.0, (5.0 - avg_satisfaction) / 4.0 * 10.0)
                survey_risk_score += sum(1 for response in responses if response.money_spent_properly == "no") / response_count * 5.0
                if response_rate < 0.2:
                    survey_risk_score += 3.0

            survey_risk_score = round(min(survey_risk_score, 30.0), 2)
            metadata = dict(project.metadata_json or {})
            base_score = float(metadata.get("final_risk_score") or project.risk_score or 0.0)
            previous_survey = float(metadata.get("survey_risk_score") or 0.0)
            updated_score = round(min(max(base_score - previous_survey, 0.0) + survey_risk_score, 100.0), 2)

            metadata["survey_risk_score"] = survey_risk_score
            metadata["final_risk_score"] = updated_score
            project.metadata_json = metadata
            project.risk_score = updated_score
            project.risk_level = RiskLevel.CRITICAL if updated_score >= 75 else RiskLevel.HIGH if updated_score >= 50 else RiskLevel.MEDIUM if updated_score >= 30 else RiskLevel.LOW
            db.commit()
            return updated_score
        finally:
            db.close()

    def _phones_for_location(self, district: str) -> List[str]:
        return list(self.DEMO_PHONES.get(str(district or "").strip(), self.DEMO_PHONES["default"]))

    @staticmethod
    def _find_project(db, project_id: str) -> Optional[Project]:
        try:
            numeric_id = int(project_id)
            project = db.query(Project).filter(Project.id == numeric_id).first()
            if project:
                return project
        except (TypeError, ValueError):
            pass

        for project in db.query(Project).all():
            if str((project.metadata_json or {}).get("project_id", "")) == str(project_id):
                return project
        return None


survey_dispatcher = SurveyDispatcher()

try:
    from celery import Celery
    from config import settings

    celery_app = Celery("survey_tasks", broker=settings.redis_url, backend=settings.redis_url)

    @celery_app.task(name="survey_dispatcher.dispatch_project_survey")
    def dispatch_project_survey(project_id: str, project_name: str, mp_name: str, district: str, state: str) -> Dict[str, Any]:
        """Celery task wrapper for survey dispatch."""
        return survey_dispatcher.dispatch_survey(project_id, project_name, mp_name, district, state)

except Exception:
    celery_app = None
    dispatch_project_survey = None
