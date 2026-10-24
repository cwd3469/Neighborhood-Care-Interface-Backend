from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AiSummaryResponse(BaseModel):
    id: int
    record_id: int
    summary: str
    anomaly_flags: Optional[list[str]] = None
    generated_at: datetime
    model_used: str

    class Config:
        from_attributes = True


class SeniorAiSummaryResponse(BaseModel):
    id: int
    senior_id: int
    trend_summary: str
    anomaly_flags: Optional[list[str]] = None
    recommendations: Optional[list[str]] = None
    record_count: int
    generated_at: datetime
    model_used: str

    class Config:
        from_attributes = True
