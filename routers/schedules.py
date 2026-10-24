from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.schedule import ScheduleCreate, ScheduleUpdate, ScheduleStatusUpdate, ScheduleResponse
from services.schedule_service import (
    create_schedule, get_schedules, get_schedule,
    update_schedule, update_schedule_status, delete_schedule,
)
from routers.users import get_current_user, require_admin
from models import User, UserRole

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=list[ScheduleResponse])
def list_schedules(
    senior_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == UserRole.caregiver:
        return get_schedules(db, caregiver_id=current_user.id, senior_id=senior_id)
    # guardian은 자기 어르신 일정만 — senior_id 필수 필터는 프론트에서 처리
    return get_schedules(db, senior_id=senior_id)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def read_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_schedule(schedule_id, db)


@router.post("", response_model=ScheduleResponse)
def create(
    data: ScheduleCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return create_schedule(data, created_by=current_user.id, db=db)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update(
    schedule_id: int,
    data: ScheduleUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return update_schedule(schedule_id, data, db)


@router.patch("/{schedule_id}/status", response_model=ScheduleResponse)
def change_status(
    schedule_id: int,
    data: ScheduleStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return update_schedule_status(schedule_id, data.status, db)


@router.delete("/{schedule_id}")
def delete(
    schedule_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return delete_schedule(schedule_id, db)
