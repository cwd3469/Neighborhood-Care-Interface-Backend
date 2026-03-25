from datetime import datetime  # ← 이게 핵심
from pydantic import BaseModel
from typing import Optional

# Pydantic 스키마
class QuestionnaireCreate(BaseModel):
    name: str
    description: Optional[str] = None
    questionnaire: str

class QuestionnaireUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    questionnaire: str

class QuestionnaireResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    questionnaire: str
    created_on: datetime
    modified_on: datetime

    class Config:
        from_attributes = True  # orm_mode → from_attributes