"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class RiskLevelEnum(str):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ── Vendor Schemas ─────────────────────────────────────────────────────────
class VendorBase(BaseModel):
    name: str
    registration_number: Optional[str] = None
    pan_number: Optional[str] = None
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class VendorCreate(VendorBase):
    pass


class VendorRead(VendorBase):
    id: int
    blacklisted: bool
    risk_score: float
    total_contracts: int
    total_contract_value: float
    created_at: datetime

    class Config:
        from_attributes = True


# ── Project Schemas ────────────────────────────────────────────────────────
class ProjectBase(BaseModel):
    title: str
    description: Optional[str] = None
    mp_constituency: Optional[str] = None
    mp_name: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    allocated_amount: float
    disbursed_amount: float = 0.0
    expenditure: float = 0.0
    status: Optional[str] = "PROPOSED"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    start_date: Optional[datetime] = None
    completion_date: Optional[datetime] = None
    vendor_id: Optional[int] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectRead(ProjectBase):
    id: int
    risk_level: str
    risk_score: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectDetail(ProjectRead):
    flags: List["FlagRead"] = []
    vendor: Optional[VendorRead] = None


# ── Flag Schemas ───────────────────────────────────────────────────────────
class FlagBase(BaseModel):
    flag_type: str
    severity: str = "MEDIUM"
    description: str
    engine_source: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None


class FlagCreate(FlagBase):
    project_id: Optional[int] = None
    vendor_id: Optional[int] = None


class FlagRead(FlagBase):
    id: int
    project_id: Optional[int]
    vendor_id: Optional[int]
    resolved: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Survey Schemas ─────────────────────────────────────────────────────────
class SurveyResponseCreate(BaseModel):
    project_id: int
    respondent_phone: Optional[str] = None
    respondent_type: Optional[str] = "citizen"
    work_quality_score: Optional[int] = Field(None, ge=1, le=5)
    work_completed: Optional[bool] = None
    bribery_reported: bool = False
    comments: Optional[str] = None


class SurveyResponseRead(SurveyResponseCreate):
    id: int
    sentiment_score: Optional[float]
    survey_date: datetime

    class Config:
        from_attributes = True


class SurveyDispatchResponse(BaseModel):
    batch_id: str
    phones_queued: int
    project_id: str


class CitizenSurveySubmit(BaseModel):
    saw_project: bool
    quality_score: int = Field(..., ge=1, le=5)
    satisfaction_score: int = Field(..., ge=1, le=5)
    money_spent_properly: Literal["yes", "no", "unsure"]
    comments: str = ""


class CitizenSurveyThankYou(BaseModel):
    thank_you: str


class CitizenSurveyPublicLink(BaseModel):
    project_id: str
    work_name: str
    mp_name: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    amount: float
    survey_url: str


class CitizenSurveyResponseItem(BaseModel):
    id: int
    saw_project: Optional[bool] = None
    quality_score: Optional[int] = None
    satisfaction_score: Optional[int] = None
    money_spent_properly: Optional[str] = None
    comments: Optional[str] = None
    sentiment_score: Optional[float] = None
    survey_date: datetime


class CitizenSurveyResults(BaseModel):
    sent_count: int
    response_count: int
    response_rate: float
    avg_satisfaction: float
    aware_citizens_pct: float
    common_issues: List[str]
    all_responses: List[CitizenSurveyResponseItem]


# ── Dashboard Schemas ──────────────────────────────────────────────────────
class DashboardStats(BaseModel):
    total_projects: int
    total_amount_crore: float
    high_risk_projects: int
    flags_raised: int
    vendors_monitored: int
    blacklisted_vendors: int
    surveys_collected: int
    avg_risk_score: float


class RiskDistribution(BaseModel):
    LOW: int
    MEDIUM: int
    HIGH: int
    CRITICAL: int


class StateWiseRisk(BaseModel):
    state: str
    total_projects: int
    avg_risk_score: float
    total_amount: float


# ── Ingestion Schemas ──────────────────────────────────────────────────────
class IngestionResponse(BaseModel):
    message: str
    records_processed: int
    errors: List[str] = []


ProjectDetail.model_rebuild()
