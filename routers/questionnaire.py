from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from schemas.questionnaire import QuestionnaireCreate, QuestionnaireUpdate, QuestionnaireResponse
from services.questionnaire_service import get_all_questionnaires, get_questionnaire, create_questionnaire, update_questionnaire, delete_questionnaire
from routers.users import get_current_user
from models import User

router = APIRouter(prefix="/questionnaire", tags=["questionnaires"])

@router.get("/", response_model=list[QuestionnaireResponse])
def read_all_questionnaires(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_all_questionnaires(db)

@router.get("/{questionnaire_id}", response_model=QuestionnaireResponse)
def read_questionnaire(questionnaire_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_questionnaire(questionnaire_id, db)

@router.post("/", response_model=QuestionnaireResponse)
def write_questionnaire(questionnaire: QuestionnaireCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return create_questionnaire(questionnaire, db)

@router.put("/{questionnaire_id}", response_model=QuestionnaireResponse)
def modify_questionnaire(questionnaire_id: int, questionnaire: QuestionnaireUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return update_questionnaire(questionnaire_id, questionnaire, db)

@router.delete("/{questionnaire_id}")
def remove_questionnaire(questionnaire_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return delete_questionnaire(questionnaire_id, db)
