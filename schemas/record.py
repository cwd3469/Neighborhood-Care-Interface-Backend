from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class VisitRecordCreate(BaseModel):
    senior_id: int
    schedule_id: Optional[int] = None
    fhir_response: dict[str, Any]   # FHIR QuestionnaireResponse JSON
    visit_notes: Optional[str] = None


class VisitRecordResponse(BaseModel):
    id: int
    senior_id: int
    caregiver_id: int
    schedule_id: Optional[int] = None
    fhir_response: dict[str, Any]
    visit_notes: Optional[str] = None
    recorded_at: datetime

    class Config:
        from_attributes = True
