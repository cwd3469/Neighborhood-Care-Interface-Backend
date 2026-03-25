from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import Questionnaire
from schemas.questionnaire import QuestionnaireCreate, QuestionnaireUpdate

def get_all_questionnaires(db: Session):
    return db.query(Questionnaire).all()

def get_questionnaire(questionnaire_id: int, db: Session):
    questionnaire = db.query(Questionnaire).filter(Questionnaire.id == questionnaire_id).first()
    if not questionnaire:
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없습니다")
    return questionnaire


def create_questionnaire(questionnaire: QuestionnaireCreate, db: Session):
    db_questionnaire = Questionnaire(**questionnaire.dict())
    db.add(db_questionnaire)
    db.commit()
    db.refresh(db_questionnaire)
    return db_questionnaire


def update_questionnaire(questionnaire_id: int, questionnaire: QuestionnaireUpdate, db: Session):
    db_questionnaire = db.query(Questionnaire).filter(Questionnaire.id == questionnaire_id).first()
    if not db_questionnaire:
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없습니다")

    for key, value in questionnaire.dict(exclude_unset=True).questionnaires():
        setattr(db_questionnaire, key, value)

    db.commit()
    db.refresh(db_questionnaire)
    return db_questionnaire


def delete_questionnaire(questionnaire_id: int, db: Session):
    db_questionnaire = db.query(Questionnaire).filter(Questionnaire.id == questionnaire_id).first()
    if not db_questionnaire:
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없습니다")

    db.delete(db_questionnaire)
    db.commit()
    return {"message": "삭제 완료", "id": questionnaire_id}