from pydantic import BaseModel
from typing import Optional
from datetime import date, time, datetime
from models import ScheduleStatus


class ScheduleCreate(BaseModel):
    senior_id: int
    caregiver_id: int
    scheduled_date: date
    start_time: time
    end_time: time
    notes: Optional[str] = None


class ScheduleUpdate(BaseModel):
    scheduled_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    caregiver_id: Optional[int] = None
    notes: Optional[str] = None


class ScheduleStatusUpdate(BaseModel):
    status: ScheduleStatus


class ScheduleResponse(BaseModel):
    id: int
    senior_id: int
    caregiver_id: int
    scheduled_date: date
    start_time: time
    end_time: time
    status: ScheduleStatus
    notes: Optional[str] = None
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True
