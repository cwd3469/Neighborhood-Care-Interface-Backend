import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime,
    Date, Time, Boolean, ForeignKey, Enum, JSON, UniqueConstraint
)
from database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    caregiver = "caregiver"
    guardian = "guardian"


class ScheduleStatus(str, enum.Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Senior(Base):
    """돌봄 대상 어르신"""
    __tablename__ = "seniors"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    birth_date = Column(Date, nullable=False)
    gender = Column(String, nullable=False)  # M / F
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    medical_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class GuardianSeniorRelation(Base):
    """보호자 ↔ 어르신 관계 매핑"""
    __tablename__ = "guardian_senior_relations"
    __table_args__ = (UniqueConstraint("guardian_id", "senior_id"),)

    id = Column(Integer, primary_key=True, index=True)
    guardian_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    senior_id = Column(Integer, ForeignKey("seniors.id"), nullable=False)
    relation = Column(String, nullable=True)  # 자녀, 배우자, 형제 등


class VisitSchedule(Base):
    """방문 일정"""
    __tablename__ = "visit_schedules"

    id = Column(Integer, primary_key=True, index=True)
    senior_id = Column(Integer, ForeignKey("seniors.id"), nullable=False)
    caregiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(Enum(ScheduleStatus), default=ScheduleStatus.scheduled, nullable=False)
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class VisitRecord(Base):
    """방문 기록 — FHIR QuestionnaireResponse 원본 JSONB 저장"""
    __tablename__ = "visit_records"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("visit_schedules.id"), nullable=True)
    caregiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    senior_id = Column(Integer, ForeignKey("seniors.id"), nullable=False)
    fhir_response = Column(JSON, nullable=False)   # FHIR QuestionnaireResponse
    visit_notes = Column(Text, nullable=True)       # 자유 텍스트 메모
    recorded_at = Column(DateTime, default=datetime.utcnow)


class VitalObservation(Base):
    """활력징후 구조화 — FHIR Observation + LOINC 코드 (대시보드·추이 쿼리용)"""
    __tablename__ = "vital_observations"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("visit_records.id"), nullable=False)
    senior_id = Column(Integer, ForeignKey("seniors.id"), nullable=False)
    loinc_code = Column(String, nullable=False)    # e.g. "8480-6"
    display_name = Column(String, nullable=False)  # e.g. "혈압(수축기)"
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)          # e.g. "mmHg"
    observed_at = Column(DateTime, nullable=False)
    fhir_observation = Column(JSON, nullable=True) # FHIR Observation 원본


class AiSummary(Base):
    """LLM이 생성한 방문 기록 요약 및 이상징후"""
    __tablename__ = "ai_summaries"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("visit_records.id"), unique=True, nullable=False)
    summary = Column(Text, nullable=False)
    anomaly_flags = Column(JSON, nullable=True)  # list[str]
    generated_at = Column(DateTime, default=datetime.utcnow)
    model_used = Column(String, nullable=False)


class SeniorAiSummary(Base):
    # Design Ref: §2.1 — senior 단위 누적 방문기록 종합 요약, upsert 패턴
    __tablename__ = "senior_ai_summaries"

    id              = Column(Integer, primary_key=True, index=True)
    senior_id       = Column(Integer, ForeignKey("seniors.id"), unique=True, nullable=False)
    trend_summary   = Column(Text, nullable=False)
    anomaly_flags   = Column(JSON, nullable=True)    # list[str]
    recommendations = Column(JSON, nullable=True)    # list[str]
    record_count    = Column(Integer, nullable=False)
    generated_at    = Column(DateTime, default=datetime.utcnow)
    model_used      = Column(String, nullable=False)


class RefreshToken(Base):
    # Design Ref: §2.1 — 다중 기기 지원, 원문 미저장(해시만 보관)
    __tablename__ = "refresh_tokens"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash  = Column(String, nullable=False, index=True)
    expires_at  = Column(DateTime, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
    device_info = Column(String, nullable=True)
