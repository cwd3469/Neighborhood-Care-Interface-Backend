from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class SeniorCreate(BaseModel):
    full_name: str
    birth_date: date
    gender: str       # "M" or "F"
    address: Optional[str] = None
    phone: Optional[str] = None
    medical_notes: Optional[str] = None


class SeniorUpdate(BaseModel):
    full_name: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    medical_notes: Optional[str] = None


class SeniorResponse(BaseModel):
    id: int
    full_name: str
    birth_date: date
    gender: str
    address: Optional[str] = None
    phone: Optional[str] = None
    medical_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GuardianRelationCreate(BaseModel):
    guardian_id: int
    relation: Optional[str] = None  # 자녀, 배우자, 형제 등


class GuardianRelationResponse(BaseModel):
    id: int
    guardian_id: int
    senior_id: int
    relation: Optional[str] = None

    class Config:
        from_attributes = True
