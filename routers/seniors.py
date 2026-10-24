from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.senior import SeniorCreate, SeniorUpdate, SeniorResponse, GuardianRelationCreate, GuardianRelationResponse
from services.senior_service import (
    get_all_seniors, get_senior, create_senior, update_senior, delete_senior,
    add_guardian_relation, get_guardian_relations, get_seniors_for_guardian,
)
from routers.users import get_current_user, require_admin
from models import User, UserRole

router = APIRouter(prefix="/seniors", tags=["seniors"])


@router.get("", response_model=list[SeniorResponse])
def list_seniors(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == UserRole.guardian:
        return get_seniors_for_guardian(current_user.id, db)
    return get_all_seniors(db)


@router.get("/{senior_id}", response_model=SeniorResponse)
def read_senior(
    senior_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_senior(senior_id, db)


@router.post("", response_model=SeniorResponse)
def create(
    data: SeniorCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return create_senior(data, db)


@router.put("/{senior_id}", response_model=SeniorResponse)
def update(
    senior_id: int,
    data: SeniorUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return update_senior(senior_id, data, db)


@router.delete("/{senior_id}")
def delete(
    senior_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return delete_senior(senior_id, db)


@router.post("/{senior_id}/guardians", response_model=GuardianRelationResponse)
def assign_guardian(
    senior_id: int,
    data: GuardianRelationCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return add_guardian_relation(senior_id, data, db)


@router.get("/{senior_id}/guardians", response_model=list[GuardianRelationResponse])
def list_guardians(
    senior_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_guardian_relations(senior_id, db)
