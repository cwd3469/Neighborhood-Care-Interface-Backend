from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from schemas.user import UserCreate, UserResponse, Token
from services.user_service import register_user, login_user, get_users, deactivate_user
from auth import decode_access_token
from models import User, UserRole

router = APIRouter(tags=["auth"])

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_user(
    token: str = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    username = decode_access_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="토큰이 유효하지 않습니다")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="유저를 찾을 수 없습니다")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="비활성화된 계정입니다")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    return current_user


def require_caregiver_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.admin, UserRole.caregiver):
        raise HTTPException(status_code=403, detail="요양사 또는 관리자 권한이 필요합니다")
    return current_user


@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    return register_user(user, db)


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return login_user(form_data.username, form_data.password, db)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/admin/users", response_model=UserResponse)
def create_user(
    user: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return register_user(user, db)


@router.get("/admin/users", response_model=list[UserResponse])
def list_users(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return get_users(db)


@router.patch("/admin/users/{user_id}/deactivate", response_model=UserResponse)
def deactivate(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return deactivate_user(user_id, db)
