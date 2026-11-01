from typing import Optional
from fastapi import APIRouter, Depends , HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas.schedule import ScheduleCreate, ScheduleUpdate, ScheduleStatusUpdate, ScheduleResponse
from services.schedule_service import (
    create_schedule, get_schedules, get_schedule,
    update_schedule, update_schedule_status, delete_schedule,get_schedules_for_guardian
)
from routers.users import get_current_user, require_admin , check_guardian_senior_access , require_caregiver_or_admin
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
    if current_user.role == UserRole.guardian:
        return get_schedules_for_guardian(current_user.id, db, senior_id=senior_id)
    return get_schedules(db, senior_id=senior_id)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def read_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schedule = get_schedule(schedule_id, db)  # 없으면 404

    check_guardian_senior_access(schedule.senior_id, current_user, db)  # 보호자: 남의 어르신이면 403

    if current_user.role == UserRole.caregiver and schedule.caregiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")  # 요양사: 남의 일정이면 403

    return schedule

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
    current_user: User = Depends(require_caregiver_or_admin), # ① 보호자는 여기서 403
    db: Session = Depends(get_db),
):
    # TODO ②: 일정 조회 (없으면 404)
    schedule = get_schedule(schedule_id, db)                     # ② 없으면 404

    # TODO ③: 요양사인데 내 일정이 아니면 403  ← 03번에서 쓴 그 줄
    if current_user.role == UserRole.caregiver and schedule.caregiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")  # 요양사: 남의 일정이면 403

    # TODO ④: 상태 변경 후 return
    return update_schedule_status(schedule_id, data.status, db)


@router.delete("/{schedule_id}")
def delete(
    schedule_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return delete_schedule(schedule_id, db)

