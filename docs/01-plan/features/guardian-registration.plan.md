# Plan: guardian-registration

> 보호자 등록 심화 — 어르신 필수 연결 + 복수 등록

- **Feature**: guardian-registration
- **Date**: 2026-10-09
- **Phase**: Plan

---

## Executive Summary

| 관점 | 내용 |
|------|------|
| Problem | 보호자 계정 생성 시 어르신 연결이 선택적·후처리로 분리되어 있어, 어르신 없는 보호자 계정이 생성될 수 있음 |
| Solution | `POST /admin/users`에서 보호자 role 선택 시 `senior_ids[]` 필수 입력을 받아 계정 생성과 관계 설정을 원자적으로 처리 |
| Function UX Effect | 관리자가 보호자 등록 한 번으로 어르신 연결까지 완료, 후속 API 호출 불필요 |
| Core Value | 데이터 무결성 보장 — 보호자는 반드시 담당 어르신이 존재하는 유효한 상태로만 생성됨 |

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| WHY | 보호자 역할은 어르신 없이 의미 없음. 등록 시 강제 연결로 무결성 확보 |
| WHO | 관리자(admin) — 보호자 계정 생성 주체 |
| RISK | 기존 `POST /admin/users` API 스키마 변경 → 프론트엔드 호환성 영향 |
| SUCCESS | 보호자 등록 시 어르신 1명 이상 연결 필수. 어르신 없는 보호자 계정 생성 불가 |
| SCOPE | `schemas/user.py`, `services/user_service.py`, `routers/users.py` 수정만. 모델 변경 없음 |

---

## 1. 요구사항

### 기능 요구사항

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-01 | 보호자(guardian) role로 유저 생성 시 `senior_ids: list[int]` 필드 필수 (최소 1개) | 필수 |
| FR-02 | `senior_ids`의 각 ID가 DB에 존재하는 Senior인지 검증 | 필수 |
| FR-03 | 유저 생성과 GuardianSeniorRelation 생성을 하나의 트랜잭션으로 처리 | 필수 |
| FR-04 | 복수 어르신 연결 지원 (senior_ids에 여러 ID 허용) | 필수 |
| FR-05 | admin / caregiver role로 생성 시 senior_ids는 무시하거나 Optional | 선택 |
| FR-06 | 등록된 보호자 응답에 연결된 `senior_ids` 포함 | 선택 |

### 비기능 요구사항

- 기존 caregiver/admin 등록 흐름 변경 없음 (하위 호환)
- 어르신 ID 유효성 실패 시 422 또는 400 반환

---

## 2. 현재 상태 분석

### 기존 구현

```
POST /admin/users (UserCreate)
  └─ username, password, role, full_name, phone
  └─ register_user() → User 생성 후 반환

POST /seniors/{senior_id}/guardians (별도 API)
  └─ admin만 호출 가능
  └─ GuardianSeniorRelation 생성
```

### 문제점

1. 두 API를 순서대로 호출해야 함 (비원자적)
2. 보호자 등록 후 어르신 연결을 빠뜨려도 오류 없음
3. 프론트엔드에서 2단계 처리 필요

---

## 3. 변경 범위

### 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `schemas/user.py` | `GuardianUserCreate` 스키마 추가 (senior_ids 필수), `UserCreateRequest` Union 타입 또는 `UserCreate`에 Optional `senior_ids` 추가 |
| `services/user_service.py` | `register_user`에서 role=guardian이면 senior_ids 검증 + GuardianSeniorRelation 일괄 생성 |
| `routers/users.py` | `POST /admin/users` 요청 스키마 업데이트 |

### 신규 생성 파일

없음 — 기존 파일 수정만

---

## 4. 리스크

| 리스크 | 영향도 | 대응 |
|--------|--------|------|
| 기존 프론트엔드가 `UserCreate` 스키마 그대로 사용 중일 경우 | 중 | `senior_ids`를 Optional로 추가, guardian role일 때만 서버 사이드 검증 |
| 존재하지 않는 senior_id 입력 | 중 | 각 ID 조회 후 404/422로 명시 |
| 트랜잭션 도중 부분 실패 | 낮 | SQLAlchemy rollback으로 처리 |

---

## 5. 성공 기준

- [ ] SC-01: `role=guardian` + `senior_ids=[]` 또는 미전송 시 400 오류 반환
- [ ] SC-02: `role=guardian` + 존재하지 않는 senior_id 시 400 오류 반환
- [ ] SC-03: `role=guardian` + 유효한 senior_ids 시 User + GuardianSeniorRelation 모두 생성
- [ ] SC-04: `role=admin`/`caregiver` 등록 시 senior_ids 없이 기존대로 동작
- [ ] SC-05: 복수 senior_ids(2개 이상) 모두 GuardianSeniorRelation에 등록됨

---

## 6. 구현 접근법

### Option A — UserCreate에 Optional senior_ids 추가 (권장)

```python
class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole
    full_name: Optional[str] = None
    phone: Optional[str] = None
    senior_ids: Optional[list[int]] = None  # guardian role 시 필수 검증

# register_user()에서:
if user.role == UserRole.guardian:
    if not user.senior_ids:
        raise HTTPException(400, "보호자는 어르신을 1명 이상 지정해야 합니다")
    # senior 존재 검증 + GuardianSeniorRelation 생성
```

- 장점: 스키마 단순, 프론트엔드 호환
- 단점: 필드가 role에 따라 의미 달라짐

### Option B — Union 타입 분리

```python
class GuardianCreate(UserCreate):
    senior_ids: list[int]  # 필수
```

- 장점: 타입 안전성 높음
- 단점: 라우터 변경 필요, 프론트엔드 분기 처리

**권장: Option A** — 최소 변경으로 목표 달성
