from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class VitalObservationResponse(BaseModel):
    id: int
    record_id: int
    senior_id: int
    loinc_code: str
    display_name: str
    value: float
    unit: str
    observed_at: datetime
    fhir_observation: Optional[dict[str, Any]] = None

    class Config:
        from_attributes = True
