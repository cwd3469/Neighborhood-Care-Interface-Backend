from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib
from jose import JWTError, jwt
import bcrypt
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

REFRESH_TOKEN_EXPIRE_DAYS = 7

# 비밀번호 암호화
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# 비밀번호 검증
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# JWT 토큰 생성
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# JWT 토큰 검증
def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None

# Refresh Token 생성 (원문 — 클라이언트에만 전달)
def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)

# Refresh Token 해시 (DB 저장용 — sha256, bcrypt 72바이트 제한 없음)
def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

# Refresh Token 검증
def verify_refresh_token(plain: str, hashed: str) -> bool:
    # Plan SC: SC-02, SC-03 — 원문/해시 비교로 갱신·로그아웃 검증
    return hashlib.sha256(plain.encode()).hexdigest() == hashed

