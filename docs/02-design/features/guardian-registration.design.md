# Design: guardian-registration

> 보호자 등록 심화 — Option A (최소 변경)

- **Feature**: guardian-registration
- **Date**: 2026-10-09
- **Architecture**: Option A — Minimal Changes
- **Phase**: Design

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| WHY | 보호자 역할은 어르신 없이 의미 없음. 등록 시 강제 연결로 무결성 확보 |
| WHO | 관리자(admin) — 보호자 계정 생성 주체 |
| RISK | 기존 `POST /admin/users` API 스키마 변경 → 프론트엔드 호환성 영향 |
| SUCCESS | 보호자 등록 시 어르신 1명 이상 연결 필수. 어르신 없는 보호자 계정 생성 불가 |
| SCOPE | `schemas/user.py`, `services/user_service.py` 수정만. 모델·라우터 변경 없음 |

---

## 1. 아키텍처 결정

**선택: Option A — UserCreate 확장**

기존 `UserCreate` 스키마에 `senior_ids: Optional[list[int]]` 필드를 추가하고,
`register_user()` 서비스에서 role=guardian일 때 서버 사이드 검증 + 관계 생성.

**근거:**
- API 엔드포인트 경로 변경 없음 → 프론트엔드 호환 유지
- 신규 파일 없음 → 최소 변경
- guardian이 아닌 role에서 `senior_ids` 전송해도 무시 (하위 호환)

---

## 2. 데이터 모델

### 변경 없음

기존 `GuardianSeniorRelation` 모델을 그대로 사용:

```python
class GuardianSeniorRelation(Base):
    __tablename__ = "guardian_senior_relations"
    __table_args__ = (UniqueConstraint("guardian_id", "senior_id"),)

    id = Column(Integer, primary_key=True)
    guardian_id = Column(Integer, ForeignKey("users.id"))
    senior_id   = Column(Integer, ForeignKey("seniors.id"))
    relation    = Column(String, nullable=True)
```

---

## 3. 스키마 변경 (`schemas/user.py`)

### 3.1 UserCreate 확장

```python
class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole
    full_name: Optional[str] = None
    phone: Optional[str] = None
    senior_ids: Optional[list[int]] = None  # guardian role 시 서버 검증 필수
```

### 3.2 UserResponse 변경 없음

기존 `UserResponse` 그대로 사용 (senior_ids는 응답에 포함하지 않음 — YAGNI).
필요 시 `GET /seniors?guardian_id={id}` 로 조회 가능.

---

## 4. 서비스 변경 (`services/user_service.py`)

### 4.1 register_user 확장

```python
# Design Ref: §4 — guardian role 시 senior_ids 검증 + 원자적 관계 생성
def register_user(user: UserCreate, db: Session) -> User:
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 존재하는 유저입니다")

    # Plan SC: SC-01 — guardian은 senior_ids 필수
    if user.role == UserRole.guardian:
        if not user.senior_ids:
            raise HTTPException(
                status_code=400,
                detail="보호자는 어르신을 1명 이상 지정해야 합니다"
            )
        # Plan SC: SC-02 — senior_id 존재 검증
        for sid in user.senior_ids:
            senior = db.query(Senior).filter(Senior.id == sid).first()
            if not senior:
                raise HTTPException(
                    status_code=400,
                    detail=f"어르신 ID {sid}를 찾을 수 없습니다"
                )

    db_user = User(
        username=user.username,
        hashed_password=hash_password(user.password),
        role=user.role,
        full_name=user.full_name,
        phone=user.phone,
    )
    db.add(db_user)
    db.flush()  # ID 확보 (commit 전)

    # Plan SC: SC-03, SC-05 — 원자적 트랜잭션으로 관계 일괄 생성
    if user.role == UserRole.guardian and user.senior_ids:
        for sid in user.senior_ids:
            db.add(GuardianSeniorRelation(
                guardian_id=db_user.id,
                senior_id=sid,
            ))

    db.commit()
    db.refresh(db_user)
    return db_user
```

### 4.2 핵심 변경 포인트

| 포인트 | 설명 |
|--------|------|
| `db.flush()` 사용 | commit 전에 `db_user.id` 확보 → GuardianSeniorRelation FK에 사용 |
| 단일 트랜잭션 | User + 모든 GuardianSeniorRelation을 하나의 `db.commit()`으로 처리 |
| 기존 `db.refresh` 유지 | `db.commit()` 후 db_user 최신 상태 반영 |

---

## 5. 라우터 변경 (`routers/users.py`)

### 변경 없음

`POST /admin/users`는 그대로 유지. 스키마가 자동으로 `senior_ids` 필드를 수용.

```python
@router.post("/admin/users", response_model=UserResponse)
def create_user(
    user: UserCreate,          # senior_ids 포함된 확장 스키마 그대로
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return register_user(user, db)
```

---

## 6. import 추가 (`services/user_service.py`)

```python
from models import User, RefreshToken, Senior, GuardianSeniorRelation
```

기존 `from models import User, RefreshToken`에 `Senior, GuardianSeniorRelation` 추가.

---

## 7. API 동작 명세

### 보호자 등록 성공 (복수 어르신)

```
POST /admin/users
Authorization: Bearer <admin_token>

{
  "username": "guardian01",
  "password": "pass1234",
  "role": "guardian",
  "full_name": "김보호",
  "senior_ids": [1, 2]
}

→ 200 OK
{
  "id": 6,
  "username": "guardian01",
  "role": "guardian",
  "full_name": "김보호",
  "phone": null,
  "is_active": true
}
```

### 보호자 등록 실패 — senior_ids 미전송

```
POST /admin/users
{ "username": "g2", "password": "pw", "role": "guardian" }

→ 400 Bad Request
{ "detail": "보호자는 어르신을 1명 이상 지정해야 합니다" }
```

### 보호자 등록 실패 — 존재하지 않는 senior_id

```
POST /admin/users
{ ..., "role": "guardian", "senior_ids": [999] }

→ 400 Bad Request
{ "detail": "어르신 ID 999를 찾을 수 없습니다" }
```

### 요양사/관리자 등록 — senior_ids 무시

```
POST /admin/users
{ "username": "cg1", "password": "pw", "role": "caregiver", "senior_ids": [1] }

→ 200 OK (senior_ids는 서비스에서 무시됨)
```

---

## 8. 에러 핸들링

| 케이스 | HTTP 상태 | 메시지 |
|--------|-----------|--------|
| guardian + senior_ids 없음/빈 배열 | 400 | "보호자는 어르신을 1명 이상 지정해야 합니다" |
| guardian + 존재하지 않는 senior_id | 400 | "어르신 ID {id}를 찾을 수 없습니다" |
| 중복 username | 400 | "이미 존재하는 유저입니다" |
| 비관리자 호출 | 403 | "관리자 권한이 필요합니다" |

---

## 9. 트랜잭션 흐름

```
register_user(user, db)
  ├── username 중복 체크
  ├── [guardian only] senior_ids 비어있으면 → HTTPException 400
  ├── [guardian only] 각 senior_id 존재 검증 → HTTPException 400
  ├── User 객체 생성 → db.add(db_user)
  ├── db.flush()          ← id 확보
  ├── [guardian only] GuardianSeniorRelation × N → db.add()
  └── db.commit()         ← 전체 원자적 커밋
      db.refresh(db_user)
      return db_user
```

실패 시 SQLAlchemy 자동 rollback → User도, Relation도 저장 안 됨.

---

## 10. 테스트 시나리오

| SC | 테스트 케이스 | 기대 결과 |
|----|--------------|-----------|
| SC-01 | guardian + senior_ids=[] | 400 |
| SC-01 | guardian + senior_ids 미전송 | 400 |
| SC-02 | guardian + senior_ids=[9999] (없는 ID) | 400 |
| SC-03 | guardian + senior_ids=[1] (유효) | 200, GuardianSeniorRelation 1개 생성 |
| SC-04 | caregiver (senior_ids 없음) | 200 정상 |
| SC-05 | guardian + senior_ids=[1,2] | 200, Relation 2개 생성 |

---

## 11. Implementation Guide

### 11.1 수정 순서

1. `schemas/user.py` — `UserCreate`에 `senior_ids` 필드 추가
2. `services/user_service.py` — import 추가, `register_user` 로직 수정

### 11.2 변경 요약

| 파일 | 변경 | 예상 라인 |
|------|------|-----------|
| `schemas/user.py` | `senior_ids` 필드 1줄 추가 | +1 |
| `services/user_service.py` | import 추가, guardian 검증 + flush + 관계 생성 | +~20 |

### 11.3 Session Guide

```
Module Map:
  module-1: schemas/user.py — senior_ids 필드 추가
  module-2: services/user_service.py — 검증 로직 + GuardianSeniorRelation 생성

전체 구현 단일 세션으로 가능 (변경량 최소)
```
