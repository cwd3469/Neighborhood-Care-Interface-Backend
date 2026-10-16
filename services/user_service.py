from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import User, RefreshToken, Senior, GuardianSeniorRelation, UserRole
from schemas.user import UserCreate
from auth import hash_password, verify_password, create_access_token, create_refresh_token, hash_refresh_token, REFRESH_TOKEN_EXPIRE_DAYS
from datetime import datetime, timedelta


def register_user(user: UserCreate, db: Session) -> User:
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 존재하는 유저입니다")

    # Plan SC: SC-01 — guardian은 senior_ids 필수
    if user.role == UserRole.guardian:
        if not user.senior_ids:
            raise HTTPException(status_code=400, detail="보호자는 어르신을 1명 이상 지정해야 합니다")
        # Plan SC: SC-02 — 각 senior_id 존재 검증
        for sid in user.senior_ids:
            if not db.query(Senior).filter(Senior.id == sid).first():
                raise HTTPException(status_code=400, detail=f"어르신 ID {sid}를 찾을 수 없습니다")

    db_user = User(
        username=user.username,
        hashed_password=hash_password(user.password),
        role=user.role,
        full_name=user.full_name,
        phone=user.phone,
    )
    db.add(db_user)
    db.flush()  # Design Ref: §4.2 — commit 전 id 확보

    # Plan SC: SC-03, SC-05 — 원자적 트랜잭션으로 관계 일괄 생성
    if user.role == UserRole.guardian and user.senior_ids:
        for sid in user.senior_ids:
            db.add(GuardianSeniorRelation(guardian_id=db_user.id, senior_id=sid))

    db.commit()
    db.refresh(db_user)
    return db_user


def login_user(username: str, password: str, db: Session) -> dict:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 틀렸습니다")

    access_token = create_access_token(
        data={"sub": user.username, "username": user.username, "role": user.role},
        expires_delta=timedelta(minutes=30),
    )

    # Plan SC: SC-01 — 로그인 시 refresh token 발급 및 DB 저장
    raw_refresh = create_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "refresh_token": raw_refresh,
    }


def get_users(db: Session) -> list[User]:
    return db.query(User).all()


def deactivate_user(user_id: int, db: Session) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user
