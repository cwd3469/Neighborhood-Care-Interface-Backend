from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.vital import VitalObservationResponse
from services.vital_service import get_vitals_for_senior
from routers.users import get_current_user
from models import User

router = APIRouter(prefix="/vitals", tags=["vitals"])


@router.get("/seniors/{senior_id}", response_model=list[VitalObservationResponse])
def list_vitals(
    senior_id: int,
    loinc_code: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """어르신의 활력징후 추이 조회. loinc_code 파라미터로 특정 항목만 필터링 가능."""
    return get_vitals_for_senior(senior_id, db, loinc_code=loinc_code, limit=limit)
