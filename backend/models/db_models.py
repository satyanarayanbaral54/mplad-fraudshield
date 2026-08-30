"""SQLAlchemy ORM models for MPLAD FraudShield."""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from database import Base


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ProjectStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    SANCTIONED = "SANCTIONED"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    STALLED = "STALLED"


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    registration_number = Column(String(100), unique=True, nullable=True)
    pan_number = Column(String(20), unique=True, nullable=True)
    address = Column(Text, nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    blacklisted = Column(Boolean, default=False)
    risk_score = Column(Float, default=0.0)
    total_contracts = Column(Integer, default=0)
    total_contract_value = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    projects = relationship("Project", back_populates="vendor")
    flags = relationship("Flag", back_populates="vendor")

    def __repr__(self):
        return f"<Vendor id={self.id} name={self.name}>"


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    description = Column(Text, nullable=True)
    mp_constituency = Column(String(255), nullable=True)
    mp_name = Column(String(255), nullable=True)
    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    allocated_amount = Column(Float, nullable=False)
    disbursed_amount = Column(Float, default=0.0)
    expenditure = Column(Float, default=0.0)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PROPOSED)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.LOW)
    risk_score = Column(Float, default=0.0)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    start_date = Column(DateTime, nullable=True)
    completion_date = Column(DateTime, nullable=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vendor = relationship("Vendor", back_populates="projects")
    flags = relationship("Flag", back_populates="project")
    survey_responses = relationship("SurveyResponse", back_populates="project")
    geo_checkpoints = relationship("GeoCheckpoint", back_populates="project")

    def __repr__(self):
        return f"<Project id={self.id} title={self.title[:30]}>"


class Flag(Base):
    __tablename__ = "flags"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    flag_type = Column(String(100), nullable=False, index=True)
    severity = Column(Enum(RiskLevel), default=RiskLevel.MEDIUM)
    description = Column(Text, nullable=False)
    engine_source = Column(String(100), nullable=True)  # which engine raised it
    evidence = Column(JSON, nullable=True)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="flags")
    vendor = relationship("Vendor", back_populates="flags")

    def __repr__(self):
        return f"<Flag id={self.id} type={self.flag_type} severity={self.severity}>"


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    respondent_phone = Column(String(20), nullable=True)
    respondent_type = Column(String(50), nullable=True)  # citizen, contractor, official
    work_quality_score = Column(Integer, nullable=True)  # 1-5
    work_completed = Column(Boolean, nullable=True)
    satisfaction_score = Column(Integer, nullable=True)  # 1-5
    money_spent_properly = Column(String(20), nullable=True)  # yes, no, unsure
    bribery_reported = Column(Boolean, default=False)
    comments = Column(Text, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    batch_id = Column(String(100), nullable=True, index=True)
    survey_date = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="survey_responses")

    def __repr__(self):
        return f"<SurveyResponse id={self.id} project_id={self.project_id}>"


class SurveyBatch(Base):
    __tablename__ = "survey_batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(100), unique=True, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    provider = Column(String(50), nullable=False, default="SIMULATED")
    phones_queued = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    message = Column(Text, nullable=True)
    phones = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project")

    def __repr__(self):
        return f"<SurveyBatch batch_id={self.batch_id} project_id={self.project_id}>"


class GeoCheckpoint(Base):
    __tablename__ = "geo_checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    check_type = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    osm_data = Column(JSON, nullable=True)
    satellite_verified = Column(Boolean, default=False)
    anomaly_detected = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="geo_checkpoints")

    def __repr__(self):
        return f"<GeoCheckpoint id={self.id} project_id={self.project_id}>"
