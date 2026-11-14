from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas.record import VisitRecordCreate, VisitRecordResponse
from schemas.vital import VitalObservationResponse
from services.record_service import (
    create_record, get_records, get_record, get_records_for_guardian, get_records_for_caregiver,
)
from services.vital_service import get_vitals_for_record
from services.schedule_service import get_schedule
from routers.users import get_current_user, require_caregiver_or_admin, check_senior_access
from models import User, UserRole

router = APIRouter(prefix="/records", tags=["records"])


@router.get("", response_model=list[VisitRecordResponse])
def list_records(
    senior_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == UserRole.caregiver:
        # B2: 담당 어르신의 기록 전체 (다른 요양사가 쓴 기록 포함)
        return get_records_for_caregiver(current_user.id, db, senior_id=senior_id)
    if current_user.role == UserRole.guardian:
        # guardian은 자신의 어르신 기록만 반환 (IDOR 방어)
        return get_records_for_guardian(current_user.id, db, senior_id=senior_id)
    return get_records(db, senior_id=senior_id)


@router.get("/{record_id}", response_model=VisitRecordResponse)
def read_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_record(record_id, db)
    # Plan SC: FR-04 — guardian 소유 검사 (record의 senior_id 기준)
    check_senior_access(record.senior_id, current_user, db)
    return record


@router.get("/{record_id}/vitals", response_model=list[VitalObservationResponse])
def read_record_vitals(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_record(record_id, db)
    # Plan SC: FR-05 — guardian 소유 검사
    check_senior_access(record.senior_id, current_user, db)
    return get_vitals_for_record(record_id, db)


@router.post("", response_model=VisitRecordResponse)
def create(
    data: VisitRecordCreate,
    current_user: User = Depends(require_caregiver_or_admin),
    db: Session = Depends(get_db),
):
    # ① 담당 어르신 검사 — 요청 body의 senior_id 기준 (담당 아니면 403)
    check_senior_access(data.senior_id, current_user, db)

    # ②③ 일정을 같이 보낸 경우에만 일정과의 정합성 검사
    if data.schedule_id is not None:
        schedule = get_schedule(data.schedule_id, db)          # 없으면 404
        if schedule.senior_id != data.senior_id:
            raise HTTPException(status_code=400, detail="일정의 어르신과 기록의 어르신이 다릅니다")
        if current_user.role == UserRole.caregiver and schedule.caregiver_id != current_user.id:
            raise HTTPException(status_code=403, detail="본인 일정에만 기록할 수 있습니다")

    return create_record(data, caregiver_id=current_user.id, db=db)

