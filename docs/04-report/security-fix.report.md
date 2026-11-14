# Report: security-fix — 역할 고정 & 접근 제어(IDOR) 수정

**작성일**: 2026-11-14
**Phase**: Completed
**관련 문서**: [Plan](../01-plan/features/security-fix.plan.md) · [Analysis](../03-analysis/security-fix.analysis.md)
**검증**: pytest 권한 회귀 테스트 35개 통과 (`tests/test_permissions.py`)

---

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Problem** | `/register`가 body의 role을 그대로 저장해 누구나 admin 생성 가능. 어르신·기록·활력징후·AI 요약 API가 소유 여부를 확인하지 않아 id만 바꾸면 남의 데이터 조회 가능(IDOR). 요양사는 담당 여부와 관계없이 모든 어르신 데이터에 접근 가능 |
| **Solution** | role 고정, 어르신 단위 접근 검사 헬퍼(`check_senior_access`)를 단건 API에 적용, 목록 API는 쿼리 필터로 범위 제한. 요양사 "담당"을 일정 기반(B안)으로 정의 |
| **Function UX Effect** | 정상 사용자의 흐름은 그대로. 권한 밖 단건 요청은 403, 목록은 범위 밖 데이터가 빠짐 |
| **Core Value** | 의료·돌봄 데이터의 Broken Access Control(OWASP A01) 제거 + 회귀 테스트로 재발 방지 |

---

## 1. 수정한 취약점

| ID | 내용 | 수정 | 테스트 |
|----|------|------|--------|
| V1 | `/register` 권한 상승 | role을 caregiver로 강제, 관리자·보호자는 `POST /admin/users`로만 생성 | `test_register_forces_caregiver_role`, `test_non_admin_cannot_create_user` |
| V2 | 어르신 상세 IDOR | `check_senior_access` | `test_read_senior_access` |
| V3 | 방문 기록 상세 IDOR | `record.senior_id` 기준 검사 | `test_read_record_and_vitals_access` |
| V4 | 기록별 활력징후 IDOR | 동일 | `test_read_record_and_vitals_access` |
| V5 | 어르신 활력징후 추이 IDOR | `check_senior_access` | `test_senior_vitals_access` |
| V6 | AI 요약 4개 IDOR | LLM 호출 전에 검사 | `test_ai_endpoints_block_other_guardian` |
| G-01 | 보호자 기록 목록이 전체로 새는 문제 | 보호자 전용 쿼리 | `test_record_list_scoped_by_role` |

## 2. Plan 이후 확장한 범위

Plan은 보호자만 대상으로 했지만, 구현 중 요양사도 같은 문제가 있음을 확인해 범위를 넓혔다.

| 항목 | 결정 / 구현 |
|------|-------------|
| 일정 목록 | 보호자는 연결된 어르신 일정만 (`get_schedules_for_guardian`) |
| 일정 상세 | 보호자는 연결 검사, 요양사는 본인 일정만 |
| 일정 상태 변경 | 관리자 + 담당 요양사만 (보호자 403, 다른 요양사 403) |
| 요양사 담당 기준 | **B안(일정 기반)** — 그 어르신 일정이 1건 이상이면 담당. 배정 테이블(C안)로 바꿀 때는 `services/access_service.py`만 교체 |
| 요양사 기록 목록 | **B2** — 담당 어르신 기록 전체(작성자 무관). 상세 API와 기준을 일치시키고, 교대 요양사가 이전 기록을 볼 수 있게 함 |
| 기록 생성 | 담당 어르신만, `schedule_id`가 있으면 같은 어르신 일정(아니면 400) + 요양사는 본인 일정(아니면 403) |
| 응답 보강 | 일정 응답에 `caregiver_name` 추가 (DB 컬럼 추가 없음, relationship property) |

### 검토한 대안

| 담당 기준 | 장점 | 단점 | 결정 |
|-----------|------|------|------|
| A. 검사 없음 | 구현 0 | 요양사 IDOR 그대로 | 탈락 |
| **B. 일정 기반** | 테이블 추가 없음, 기존 데이터로 바로 동작 | 과거 일정 하나만 있어도 계속 담당으로 판단 | **채택** |
| C. 배정 테이블 | 담당 시작·종료를 명시적으로 관리 | 테이블·관리 화면 추가 필요 | 확장 시 전환 |

| 기록 목록 범위 | 장점 | 단점 | 결정 |
|----------------|------|------|------|
| B1. 본인 작성만 | 노출 최소 | 상세 API와 기준 불일치, 인수인계 어려움 | 탈락 |
| **B2. 담당 어르신 전체** | 목록·상세 일관, 돌봄 연속성 | 같은 어르신의 다른 요양사 기록 노출 | **채택** |

## 3. 변경 파일

| 파일 | 내용 |
|------|------|
| `routers/users.py` | `check_senior_access` (보호자·요양사), `/register` role 고정 |
| `services/access_service.py` | 신규 — 요양사 담당 관계 정의 (서브쿼리 / 단건 검사) |
| `routers/seniors.py`, `services/senior_service.py` | 상세 검사, 요양사 목록 범위 |
| `routers/schedules.py`, `services/schedule_service.py` | 보호자 목록 범위, 상세 검사, 상태 변경 권한 |
| `routers/records.py`, `services/record_service.py` | 상세·활력징후 검사, 보호자/요양사(B2) 목록 범위, 생성 정합성 |
| `routers/vitals.py`, `routers/ai.py` | 접근 검사 |
| `models.py`, `schemas/schedule.py` | `caregiver_name` |
| `tests/` | 신규 — pytest + SQLite 인메모리, 권한 회귀 테스트 35개 |

## 4. 남은 일 / 한계

- **운영 반영**: Render 재배포 후 운영 환경에서 403/200 재확인 필요 (마무리 작업 13번)
- **프론트 403 처리**: 보호자·요양사 계정으로 실제 화면 확인 필요 (16번)
- B안의 한계: 일정이 끝난 뒤에도 담당으로 남는다. 담당 종료가 필요해지면 C안으로 전환
- `create_all` 기반이라 스키마 변경 이력 관리가 없음 (Alembic은 마무리 범위 밖)
