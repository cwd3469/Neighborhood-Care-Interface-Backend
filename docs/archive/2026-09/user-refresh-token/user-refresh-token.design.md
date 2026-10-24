# Design: user-refresh-token — Refresh Token 만료 및 갱신 관리

**작성일**: 2026-09-25
**Phase**: Design
**Feature ID**: user-refresh-token
**선택 설계안**: Option C — 실용적 균형

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| **WHY** | 요양사/보호자가 현장 업무 중 세션 만료로 업무가 끊기는 문제 해결 |
| **WHO** | 요양사(caregiver), 보호자(guardian), 관리자(admin) — 모든 역할 |
| **RISK** | Refresh Token 탈취 시 7일간 계정 접근 가능 → HTTPS 필수, 해시 저장 |
| **SUCCESS** | 로그인 후 7일간 재로그인 없이 서비스 이용, 로그아웃 시 즉시 무효화 |
| **SCOPE** | 백엔드 FastAPI만 — 프론트 코드 수정 제외 |

---

## 1. 아키텍처 개요

### 1.1 선택 근거 (Option C)

기존 `routers/users.py`와 `services/user_service.py`는 최소한만 수정하고,
Refresh Token 전용 레이어(`routers/auth.py`, `services/auth_service.py`)를 추가한다.
다중 기기 지원을 위해 `refresh_tokens` 별도 테이블을 사용한다.

### 1.2 전체 흐름

```
[로그인] POST /login
  users.router → user_service.login_user()
    → create_access_token()   (auth.py, 기존)
    → create_refresh_token()  (auth.py, 신규)
    → RefreshToken DB 저장
    → { access_token, refresh_token, token_type, role }

[갱신] POST /auth/refresh
  auth.router → auth_service.refresh_access_token()
    → DB에서 token_hash 조회
    → 만료 확인
    → create_access_token() 새로 발급
    → { access_token, token_type }

[로그아웃] POST /auth/logout
  auth.router → auth_service.logout()
    → DB에서 해당 refresh_token 행 삭제
    → { message: "로그아웃 완료" }
```

---

## 2. 데이터 모델

### 2.1 RefreshToken 모델 (`models.py` 추가)

```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash  = Column(String, nullable=False, index=True)  # bcrypt 해시
    expires_at  = Column(DateTime, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
    device_info = Column(String, nullable=True)               # User-Agent 등
```

**설계 결정:**
- `token_hash` 인덱싱 → `/auth/refresh` 조회 성능 확보
- `ondelete="CASCADE"` → 유저 삭제 시 토큰 자동 정리
- `device_info` nullable → 다중 기기 식별 (추후 확장)

### 2.2 Refresh Token 원문 형식

```
{user_id}.{uuid4}.{timestamp}
```
- `secrets.token_urlsafe(64)` 로 생성 (opaque token)
- 원문은 클라이언트에만 전달, DB에는 `bcrypt.hashpw()` 해시만 저장

---

## 3. auth.py 변경

### 3.1 신규 함수

```python
import secrets

REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_refresh_token() -> str:
    """원문 생성 — 클라이언트에 전달"""
    return secrets.token_urlsafe(64)

def hash_refresh_token(token: str) -> str:
    """DB 저장용 해시"""
    return bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()

def verify_refresh_token(plain: str, hashed: str) -> bool:
    """원문 vs 해시 검증"""
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

---

## 4. 스키마 변경 (`schemas/user.py`)

### 4.1 Token 스키마

```python
class Token(BaseModel):
    access_token: str
    token_type: str
    role: UserRole
    refresh_token: str          # 신규 추가
```

### 4.2 신규 스키마

```python
class RefreshRequest(BaseModel):
    refresh_token: str

class RefreshResponse(BaseModel):
    access_token: str
    token_type: str

class LogoutRequest(BaseModel):
    refresh_token: str
```

---

## 5. 서비스 레이어

### 5.1 `services/user_service.py` — `login_user` 수정

```python
from auth import create_refresh_token, hash_refresh_token, REFRESH_TOKEN_EXPIRE_DAYS
from models import RefreshToken
from datetime import timedelta

def login_user(username: str, password: str, db: Session) -> dict:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 틀렸습니다")

    access_token = create_access_token(
        data={"sub": user.username, "username": user.username, "role": user.role},
        expires_delta=timedelta(minutes=30),
    )

    # Refresh Token 생성 및 저장
    raw_refresh = create_refresh_token()
    db_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(db_token)
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "refresh_token": raw_refresh,
    }
```

### 5.2 `services/auth_service.py` (신규)

```python
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import RefreshToken, User
from auth import verify_refresh_token, create_access_token
from datetime import timedelta


def refresh_access_token(raw_token: str, db: Session) -> dict:
    """Refresh Token → 새 Access Token"""
    # 만료되지 않은 토큰 목록 조회
    now = datetime.utcnow()
    candidates = db.query(RefreshToken).filter(
        RefreshToken.expires_at > now
    ).all()

    # 원문 해시 비교 (인덱스 조회 후 검증)
    matched = None
    for candidate in candidates:
        if verify_refresh_token(raw_token, candidate.token_hash):
            matched = candidate
            break

    if not matched:
        raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 Refresh Token입니다")

    user = db.query(User).filter(User.id == matched.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="유저를 찾을 수 없거나 비활성화된 계정입니다")

    new_access_token = create_access_token(
        data={"sub": user.username, "username": user.username, "role": user.role},
        expires_delta=timedelta(minutes=30),
    )
    return {"access_token": new_access_token, "token_type": "bearer"}


def logout(raw_token: str, db: Session) -> dict:
    """Refresh Token 무효화 — DB 삭제"""
    now = datetime.utcnow()
    candidates = db.query(RefreshToken).filter(
        RefreshToken.expires_at > now
    ).all()

    matched = None
    for candidate in candidates:
        if verify_refresh_token(raw_token, candidate.token_hash):
            matched = candidate
            break

    if matched:
        db.delete(matched)
        db.commit()

    return {"message": "로그아웃 완료"}
```

> **설계 결정**: 로그아웃 시 토큰이 없어도 200 반환 (멱등성 보장 — 이미 로그아웃된 상태도 성공으로 처리)

---

## 6. 라우터 (`routers/auth.py` 신규)

```python
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
```

---

## 7. main.py 변경

```python
from routers import users, seniors, schedules, records, vitals, ai, auth  # auth 추가

app.include_router(auth.router)   # 추가
```

---

## 8. 성능 / 보안 고려

### 8.1 토큰 탐색 성능

현재 구현은 만료되지 않은 전체 토큰을 조회 후 해시 비교.
사용자가 소수인 MVP 단계에서는 문제없으나, 규모 확장 시 아래 개선 고려:

- `token_hash`에 `Index` 추가 (모델에 이미 반영)
- Partial index: `WHERE expires_at > NOW()` (PostgreSQL)

### 8.2 만료 토큰 정리

요청 시점 정리 방식 사용 (별도 스케줄러 불필요):
- `/auth/refresh` 호출 시 만료 토큰 자동 제외 (`expires_at > now`)
- 주기적 정리가 필요하다면 추후 APScheduler 또는 DB cron 추가

### 8.3 보안 원칙

| 원칙 | 적용 방법 |
|------|-----------|
| 원문 DB 미저장 | bcrypt 해시만 저장 |
| 전송 보안 | HTTPS 필수 (배포 시) |
| 만료 강제 | `expires_at` 컬럼 DB 레벨 검사 |
| 로그아웃 즉시 무효화 | DB 행 삭제 |

---

## 9. API 명세

### POST /login (기존 + 변경)

**Request** (기존 동일 — OAuth2PasswordRequestForm):
```
username=string&password=string
```

**Response** (신규 필드 추가):
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "role": "caregiver",
  "refresh_token": "dGhpcyBpcyBh..."
}
```

### POST /auth/refresh

**Request**:
```json
{ "refresh_token": "dGhpcyBpcyBh..." }
```

**Response**:
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```

**Error**: `401` — 유효하지 않거나 만료된 토큰

### POST /auth/logout

**Request**:
```json
{ "refresh_token": "dGhpcyBpcyBh..." }
```

**Response**:
```json
{ "message": "로그아웃 완료" }
```

---

## 10. 엣지 케이스

| 케이스 | 처리 방식 |
|--------|-----------|
| 이미 만료된 refresh token으로 갱신 요청 | 401 반환 |
| 로그아웃 후 동일 토큰으로 재로그아웃 | 200 반환 (멱등성) |
| 유저 비활성화 후 갱신 요청 | 401 반환 |
| 유저 삭제 시 토큰 | CASCADE 삭제 자동 처리 |
| 동시 갱신 요청 (Race Condition) | MVP에서 허용 — 추후 Token Rotation으로 방지 |

---

## 11. 구현 가이드

### 11.1 구현 순서

```
1. models.py        → RefreshToken 클래스 추가
2. auth.py          → create_refresh_token, hash_refresh_token, verify_refresh_token 추가
3. schemas/user.py  → Token에 refresh_token 필드, RefreshRequest/Response/LogoutRequest 추가
4. services/user_service.py → login_user 수정 (refresh token 발급 + DB 저장)
5. services/auth_service.py → 신규 파일 생성
6. routers/auth.py  → 신규 파일 생성
7. main.py          → auth 라우터 등록
8. 서버 재시작 → DB 마이그레이션 자동 (create_all)
```

### 11.2 검증 체크리스트

- [ ] SC-01: `/login` 응답에 `refresh_token` 포함
- [ ] SC-02: 유효한 refresh_token으로 `/auth/refresh` → 새 access_token
- [ ] SC-03: `/auth/logout` 후 동일 refresh_token으로 갱신 → 401
- [ ] SC-04: 만료된 refresh_token → 401
- [ ] SC-05: 기존 `access_token`, `token_type`, `role` 응답 유지

### 11.3 Session Guide

| Module | 파일 | 예상 작업량 |
|--------|------|-------------|
| M1. 데이터 모델 | `models.py` | ~15줄 추가 |
| M2. 토큰 유틸 | `auth.py` | ~20줄 추가 |
| M3. 스키마 | `schemas/user.py` | ~15줄 추가 |
| M4. 로그인 수정 | `services/user_service.py` | ~15줄 수정 |
| M5. Auth 서비스 | `services/auth_service.py` | ~50줄 신규 |
| M6. Auth 라우터 | `routers/auth.py` | ~20줄 신규 |
| M7. 앱 등록 | `main.py` | ~2줄 수정 |

단일 세션으로 M1→M7 순서로 구현 권장. 예상 총 변경량: ~140줄.

---

## 12. 다음 단계

```
/pdca do user-refresh-token
```
