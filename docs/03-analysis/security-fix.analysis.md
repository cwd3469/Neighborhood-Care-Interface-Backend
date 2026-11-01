# Analysis: 보안 취약점 수정 — Gap 분석

> Feature: `security-fix`
> Date: 2026-10-30
> Phase: Check
> Match Rate: **100%** (Plan FR 기준) + 추가 Gap 1건 발견·수정

---

## 성공 기준 평가

| FR | 요구사항 | 상태 | 근거 |
|----|----------|------|------|
| FR-01 | `/register` role 강제 고정 | ✅ Met | `users.py:56` — `user.role = UserRole.caregiver` |
| FR-02 | `check_guardian_senior_access()` 헬퍼 | ✅ Met | `users.py:42-51` — guardian만 DB 조회, 나머지 즉시 통과 |
| FR-03 | `GET /seniors/{senior_id}` 소유 검사 | ✅ Met | `seniors.py` — 헬퍼 호출 |
| FR-04 | `GET /records/{record_id}` 소유 검사 | ✅ Met | `records.py:34` — `record.senior_id` 기준 |
| FR-05 | `GET /records/{record_id}/vitals` 소유 검사 | ✅ Met | `records.py:46` — `record.senior_id` 기준 |
| FR-06 | `GET /vitals/seniors/{senior_id}` 소유 검사 | ✅ Met | `vitals.py:23` — 헬퍼 호출 |
| FR-07 | AI 엔드포인트 4개 소유 검사 | ✅ Met | `ai.py` — 전체 4개 적용 |
| FR-08 | admin/caregiver 기존 동작 유지 | ✅ Met | 헬퍼 내 `role != guardian` 즉시 return |

**Plan Match Rate: 8/8 = 100%**

---

## 추가 발견 Gap (Plan 외)

### G-01 — `GET /records` guardian 목록 미처리 (Important)

**발견 위치**: `routers/records.py:21-23`

**문제**: guardian 역할이 caregiver 분기를 통과하지 못하고 admin과 동일한 `get_records(db, senior_id=senior_id)`로 fall-through. `senior_id` 미제공 시 전체 방문 기록 노출.

**수정**: `get_records_for_guardian()` 신규 서비스 함수 추가 + 라우터에 guardian 분기 삽입.

```
services/record_service.py — get_records_for_guardian() 추가
routers/records.py         — guardian 분기 추가
```

**수정 후 동작**:
- guardian + `senior_id=None` → 자신의 모든 어르신 기록만 반환
- guardian + `senior_id=X` (자신의 어르신) → 해당 어르신 기록 반환
- guardian + `senior_id=X` (타인 어르신) → 빈 배열 반환 (DB 쿼리에서 자연스럽게 필터)

---

## 최종 취약점 수정 현황

| 취약점 | 수정 방법 | 파일 |
|--------|-----------|------|
| V1 역할 상승 | role 강제 고정 | `routers/users.py:56` |
| V2 어르신 상세 IDOR | 소유 검사 | `routers/seniors.py` |
| V3 방문 기록 상세 IDOR | record.senior_id 소유 검사 | `routers/records.py` |
| V4 활력징후(기록) IDOR | record.senior_id 소유 검사 | `routers/records.py` |
| V5 활력징후(어르신) IDOR | 소유 검사 | `routers/vitals.py` |
| V6 AI 요약 IDOR (4개) | 소유 검사 | `routers/ai.py` |
| G-01 방문 기록 목록 IDOR | guardian 전용 쿼리 | `services/record_service.py`, `routers/records.py` |
