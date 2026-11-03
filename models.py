import enum
from datetime import date, datetime, time
from typing import Any
from sqlalchemy import (
    String, Float, Text, DateTime,
    Date, Time, Boolean, ForeignKey, Enum, JSON, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
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

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Senior(Base):
    """돌봄 대상 어르신"""
    __tablename__ = "seniors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String)
    birth_date: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String)  # M / F
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    medical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GuardianSeniorRelation(Base):
    """보호자 ↔ 어르신 관계 매핑"""
    __tablename__ = "guardian_senior_relations"
    __table_args__ = (UniqueConstraint("guardian_id", "senior_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guardian_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    senior_id: Mapped[int] = mapped_column(ForeignKey("seniors.id"))
    relation: Mapped[str | None] = mapped_column(String, nullable=True)  # 자녀, 배우자, 형제 등


class VisitSchedule(Base):
    """방문 일정"""
    __tablename__ = "visit_schedules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    senior_id: Mapped[int] = mapped_column(ForeignKey("seniors.id"))
    caregiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    scheduled_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    status: Mapped[ScheduleStatus] = mapped_column(Enum(ScheduleStatus), default=ScheduleStatus.scheduled)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VisitRecord(Base):
    """방문 기록 — FHIR QuestionnaireResponse 원본 JSONB 저장"""
    __tablename__ = "visit_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("visit_schedules.id"), nullable=True)
    caregiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    senior_id: Mapped[int] = mapped_column(ForeignKey("seniors.id"))
    fhir_response: Mapped[Any] = mapped_column(JSON)   # FHIR QuestionnaireResponse
    visit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)       # 자유 텍스트 메모
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VitalObservation(Base):
    """활력징후 구조화 — FHIR Observation + LOINC 코드 (대시보드·추이 쿼리용)"""
    __tablename__ = "vital_observations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("visit_records.id"))
    senior_id: Mapped[int] = mapped_column(ForeignKey("seniors.id"))
    loinc_code: Mapped[str] = mapped_column(String)    # e.g. "8480-6"
    display_name: Mapped[str] = mapped_column(String)  # e.g. "혈압(수축기)"
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String)          # e.g. "mmHg"
    observed_at: Mapped[datetime] = mapped_column(DateTime)
    fhir_observation: Mapped[Any | None] = mapped_column(JSON, nullable=True)  # FHIR Observation 원본


class AiSummary(Base):
    """LLM이 생성한 방문 기록 요약 및 이상징후"""
    __tablename__ = "ai_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("visit_records.id"), unique=True)
    summary: Mapped[str] = mapped_column(Text)
    anomaly_flags: Mapped[Any | None] = mapped_column(JSON, nullable=True)  # list[str]
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_used: Mapped[str] = mapped_column(String)


class SeniorAiSummary(Base):
    # Design Ref: §2.1 — senior 단위 누적 방문기록 종합 요약, upsert 패턴
    __tablename__ = "senior_ai_summaries"

    id:              Mapped[int] = mapped_column(primary_key=True, index=True)
    senior_id:       Mapped[int] = mapped_column(ForeignKey("seniors.id"), unique=True)
    trend_summary:   Mapped[str] = mapped_column(Text)
    anomaly_flags:   Mapped[Any | None] = mapped_column(JSON, nullable=True)    # list[str]
    recommendations: Mapped[Any | None] = mapped_column(JSON, nullable=True)    # list[str]
    record_count:    Mapped[int] = mapped_column()
    generated_at:    Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_used:      Mapped[str] = mapped_column(String)


class RefreshToken(Base):
    # Design Ref: §2.1 — 다중 기기 지원, 원문 미저장(해시만 보관)
    __tablename__ = "refresh_tokens"

    id:          Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id:     Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash:  Mapped[str] = mapped_column(String, index=True)
    expires_at:  Mapped[datetime] = mapped_column(DateTime)
    created_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    device_info: Mapped[str | None] = mapped_column(String, nullable=True)
