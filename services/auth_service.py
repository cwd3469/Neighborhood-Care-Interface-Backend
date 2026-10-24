# Design Ref: §5.2 — refresh/logout 비즈니스 로직 (Option C 실용적 균형)
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import RefreshToken, User
from auth import verify_refresh_token, create_access_token


def _find_matching_token(raw_token: str, db: Session) -> RefreshToken | None:
    """만료되지 않은 토큰 중 원문과 일치하는 행 반환"""
    now = datetime.utcnow()
    candidates = db.query(RefreshToken).filter(RefreshToken.expires_at > now).all()
    for candidate in candidates:
        if verify_refresh_token(raw_token, candidate.token_hash):
            return candidate
    return None


def refresh_access_token(raw_token: str, db: Session) -> dict:
    # Plan SC: SC-02 — 유효한 refresh token → 새 access token 발급
    matched = _find_matching_token(raw_token, db)
    if not matched:
        raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 Refresh Token입니다")

    user = db.query(User).filter(User.id == matched.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="유저를 찾을 수 없거나 비활성화된 계정입니다")

    # expires_delta 생략 → config의 ACCESS_TOKEN_EXPIRE_MINUTES 자동 적용
    new_access_token = create_access_token(
        data={"sub": user.username, "username": user.username, "role": user.role},
    )
    return {"access_token": new_access_token, "token_type": "bearer"}


def logout(raw_token: str, db: Session) -> dict:
    # Plan SC: SC-03 — 로그아웃 시 refresh token 즉시 무효화 (멱등성 보장)
    matched = _find_matching_token(raw_token, db)
    if matched:
        db.delete(matched)
        db.commit()
    return {"message": "로그아웃 완료"}
