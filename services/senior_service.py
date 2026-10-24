from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import Senior, GuardianSeniorRelation
from schemas.senior import SeniorCreate, SeniorUpdate, GuardianRelationCreate


def get_all_seniors(db: Session) -> list[Senior]:
    return db.query(Senior).all()


def get_seniors_for_guardian(guardian_id: int, db: Session) -> list[Senior]:
    relations = (
        db.query(GuardianSeniorRelation)
        .filter(GuardianSeniorRelation.guardian_id == guardian_id)
        .all()
    )
    senior_ids = [r.senior_id for r in relations]
    return db.query(Senior).filter(Senior.id.in_(senior_ids)).all()


def get_senior(senior_id: int, db: Session) -> Senior:
    senior = db.query(Senior).filter(Senior.id == senior_id).first()
    if not senior:
        raise HTTPException(status_code=404, detail="어르신 정보를 찾을 수 없습니다")
    return senior


def create_senior(data: SeniorCreate, db: Session) -> Senior:
    senior = Senior(**data.model_dump())
    db.add(senior)
    db.commit()
    db.refresh(senior)
    return senior


def update_senior(senior_id: int, data: SeniorUpdate, db: Session) -> Senior:
    senior = get_senior(senior_id, db)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(senior, field, value)
    db.commit()
    db.refresh(senior)
    return senior


def delete_senior(senior_id: int, db: Session) -> dict:
    senior = get_senior(senior_id, db)
    db.delete(senior)
    db.commit()
    return {"detail": "삭제되었습니다"}


def add_guardian_relation(senior_id: int, data: GuardianRelationCreate, db: Session) -> GuardianSeniorRelation:
    get_senior(senior_id, db)  # 존재 확인
    existing = (
        db.query(GuardianSeniorRelation)
        .filter(
            GuardianSeniorRelation.guardian_id == data.guardian_id,
            GuardianSeniorRelation.senior_id == senior_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="이미 등록된 보호자 관계입니다")

    relation = GuardianSeniorRelation(
        guardian_id=data.guardian_id,
        senior_id=senior_id,
        relation=data.relation,
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation


def get_guardian_relations(senior_id: int, db: Session) -> list[GuardianSeniorRelation]:
    return (
        db.query(GuardianSeniorRelation)
        .filter(GuardianSeniorRelation.senior_id == senior_id)
        .all()
    )
