# Plan: 보안 취약점 수정 — 역할 고정 & IDOR 방어

> Feature: `security-fix`
> Date: 2026-10-24
> Phase: Plan

---

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Problem** | `/register`에서 `role`을 body로 받아 누구나 admin 계정 생성 가능(권한 상승). 소유 여부 미검사로 guardian이 URL id 변경만으로 타인의 어르신 데이터 접근 가능(IDOR). |
| **Solution** | `/register`에서 role 강제 고정(`caregiver`). `routers/users.py`에 소유 검사 헬퍼 추가 후 관련 엔드포인트 6개에 적용. |
| **Function UX Effect** | 기능 변화 없음. 인가된 사용자는 동일하게 동작. 비인가 접근 시 403 반환. |
| **Core Value** | 면접·보안 감사에서 즉시 지적되는 두 가지 취약점(Broken Access Control, 역할 고정 미적용)을 제거하여 프로덕션 신뢰성 확보. |

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| **WHY** | Critical 보안 취약점 6개가 존재하며 실서비스·면접 모두에서 즉시 문제가 됨 |
| **WHO** | 모든 API 사용자 (공격자 차단, 정상 사용자 영향 없음) |
| **RISK** | `/register` role 고정 시 기존에 caregiver로 가입하던 흐름은 유지됨. admin은 `POST /admin/users`로만 생성. |
| **SUCCESS** | 6개 취약점 모두 수정, 기존 인가된 접근은 동작 유지 |
| **SCOPE** | `routers/users.py` 수정, `routers/seniors.py` · `records.py` · `vitals.py` · `ai.py` 수정 |

---

## 1. 취약점 상세

### V1 — 역할 고정 미적용 (Broken Access Control: Privilege Escalation)

**현재 코드** (`routers/users.py:42-44`):
```python
@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    return register_user(user, db)
```

`UserCreate` 스키마에 `role` 필드가 포함되어 있어 누구나 `role: "admin"` 전송 가능.

**수정**: `register_user` 호출 전 `user.role = UserRole.caregiver` 강제 고정.
관리자 계정 생성은 `POST /admin/users` (admin 인증 필요) 전용.

---

### V2~V6 — 소유 여부 미검사 (IDOR)

| ID | 엔드포인트 | guardian이 접근 가능한 타인 데이터 |
|----|------------|--------------------------------------|
| V2 | `GET /seniors/{senior_id}` | 자신과 무관한 어르신 정보 |
| V3 | `GET /records/{record_id}` | 자신이 보호하지 않는 어르신의 방문 기록 |
| V4 | `GET /records/{record_id}/vitals` | 자신이 보호하지 않는 어르신의 활력징후 |
| V5 | `GET /vitals/seniors/{senior_id}` | 자신과 무관한 어르신 활력징후 추이 |
| V6 | `POST/GET /ai/summarize`, `/ai/summary`, `/ai/senior-summary` | 자신과 무관한 어르신 AI 요약 |

**공통 원인**: guardian 역할 사용자에게 `GuardianSeniorRelation` 테이블 조회 없이 데이터 반환.

---

## 2. 요구사항

### 2.1 기능 요구사항 (FR)

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-01 | `POST /register`에서 role을 `caregiver`로 강제 고정 | Must |
| FR-02 | `routers/users.py`에 `check_guardian_senior_access(senior_id, user, db)` 헬퍼 추가 | Must |
| FR-03 | `GET /seniors/{senior_id}` — guardian이면 소유 검사 | Must |
| FR-04 | `GET /records/{record_id}` — guardian이면 record의 senior_id로 소유 검사 | Must |
| FR-05 | `GET /records/{record_id}/vitals` — guardian이면 소유 검사 | Must |
| FR-06 | `GET /vitals/seniors/{senior_id}` — guardian이면 소유 검사 | Must |
| FR-07 | AI 엔드포인트 4개 — guardian이면 소유 검사 | Must |
| FR-08 | admin · caregiver 역할은 소유 검사 없이 기존과 동일하게 동작 | Must |

### 2.2 소유 검사 로직

```python
def check_guardian_senior_access(senior_id: int, user: User, db: Session):
    """guardian 역할이면 GuardianSeniorRelation 확인. 없으면 403."""
    if user.role != UserRole.guardian:
        return  # admin/caregiver는 통과
    relation = db.query(GuardianSeniorRelation).filter(
        GuardianSeniorRelation.guardian_id == user.id,
        GuardianSeniorRelation.senior_id == senior_id,
    ).first()
    if not relation:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
```

`record_id` 기반 엔드포인트는 record 조회 후 `record.senior_id`를 추출하여 동일 함수 호출.

---

## 3. 파일별 변경 계획

| 파일 | 변경 내용 |
|------|-----------|
| `routers/users.py` | `check_guardian_senior_access()` 추가, `/register`에서 role 강제 고정 |
| `routers/seniors.py` | `GET /{senior_id}` — guardian 소유 검사 추가 |
| `routers/records.py` | `GET /{record_id}`, `GET /{record_id}/vitals` — guardian 소유 검사 추가 |
| `routers/vitals.py` | `GET /seniors/{senior_id}` — guardian 소유 검사 추가 |
| `routers/ai.py` | 4개 엔드포인트 — guardian 소유 검사 추가 |
| `services/record_service.py` | `get_record()`가 senior_id 포함한 객체 반환 확인 (변경 없을 가능성 높음) |

**변경 없는 파일**: `models.py`, `schemas/`, `services/` (대부분), `database.py`

---

## 4. 엣지 케이스

| 케이스 | 처리 |
|--------|------|
| admin이 `/register`로 가입 시도 | `caregiver`로 강제 저장됨. admin은 `POST /admin/users`만 사용 가능. |
| caregiver가 guardian 전용 소유 검사 엔드포인트 호출 | 소유 검사 skip, 기존과 동일하게 동작 |
| 존재하지 않는 record_id로 소유 검사 | record 조회에서 이미 404 반환 |
| guardian이 자신의 어르신 데이터 요청 | 정상 200 반환 |

---

## 5. 성공 기준

| 기준 | 검증 방법 |
|------|-----------|
| `POST /register`에 `role: "admin"` 전송 시 caregiver로 저장 | 응답 body의 role 확인 |
| guardian이 타인 senior_id로 `GET /seniors/{id}` 호출 시 403 | 수동 테스트 |
| guardian이 자신의 senior_id로 호출 시 200 | 수동 테스트 |
| admin/caregiver는 소유 검사 없이 기존과 동일 동작 | 수동 테스트 |
| AI 엔드포인트 4개 모두 소유 검사 적용 | 수동 테스트 |
