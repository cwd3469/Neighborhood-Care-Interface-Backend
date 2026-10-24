from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.record import VisitRecordCreate, VisitRecordResponse
from schemas.vital import VitalObservationResponse
from services.record_service import create_record, get_records, get_record
from services.vital_service import get_vitals_for_record
from routers.users import get_current_user, require_caregiver_or_admin
from models import User, UserRole

router = APIRouter(prefix="/records", tags=["records"])


@router.get("", response_model=list[VisitRecordResponse])
def list_records(
    senior_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == UserRole.caregiver:
        return get_records(db, caregiver_id=current_user.id, senior_id=senior_id)
    return get_records(db, senior_id=senior_id)


@router.get("/{record_id}", response_model=VisitRecordResponse)
def read_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_record(record_id, db)


@router.get("/{record_id}/vitals", response_model=list[VitalObservationResponse])
def read_record_vitals(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_vitals_for_record(record_id, db)


@router.post("", response_model=VisitRecordResponse)
def create(
    data: VisitRecordCreate,
    current_user: User = Depends(require_caregiver_or_admin),
    db: Session = Depends(get_db),
):
    return create_record(data, caregiver_id=current_user.id, db=db)
