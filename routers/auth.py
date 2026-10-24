from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.user import RefreshRequest, RefreshResponse, LogoutRequest
from services.auth_service import refresh_access_token, logout

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/refresh", response_model=RefreshResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    return refresh_access_token(body.refresh_token, db)


@router.post("/logout")
def do_logout(body: LogoutRequest, db: Session = Depends(get_db)):
    return logout(body.refresh_token, db)
