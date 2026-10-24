# Analysis: user-refresh-token

**작성일**: 2026-09-25
**Phase**: Check
**Match Rate**: 97%

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| **WHY** | 요양사/보호자 현장 업무 중 세션 만료로 업무 단절 해결 |
| **WHO** | caregiver, guardian, admin |
| **RISK** | Refresh Token 탈취 시 7일 노출 → bcrypt 해시 저장, HTTPS 필수 |
| **SUCCESS** | 7일간 재로그인 없이 이용, 로그아웃 시 즉시 무효화 |
| **SCOPE** | 백엔드 FastAPI만 |

---

## 성공 기준 평가

| ID | 기준 | 상태 | 근거 |
|----|------|------|------|
| SC-01 | `/login` 응답에 `refresh_token` | ✅ Met | `services/user_service.py:50` |
| SC-02 | refresh_token → 새 access_token | ✅ Met | `services/auth_service.py:19-33` |
| SC-03 | 로그아웃 후 갱신 → 401 | ✅ Met | `services/auth_service.py:36-42` |
| SC-04 | 만료 토큰 → 401 | ✅ Met | `_find_matching_token` expires_at 필터 |
| SC-05 | 기존 응답 필드 유지 | ✅ Met | `schemas/user.py:26-30` |

---

## Gap 목록

| 심각도 | 항목 | 상태 |
|--------|------|------|
| Important | `auth_service.py` expires_delta 하드코딩 30분 | ✅ 수정 완료 |
| Minor | `device_info` 미저장 (nullable, 기능 이상 없음) | 허용 (추후 확장) |

---

## 기능 요구사항 충족률

| FR | 상태 |
|----|------|
| FR-01 로그인 시 Access+Refresh 발급 | ✅ |
| FR-02 POST /auth/refresh | ✅ |
| FR-03 POST /auth/logout | ✅ |
| FR-04 bcrypt 해시 저장 | ✅ |
| FR-05 만료 토큰 401 | ✅ |
| FR-06 다중 기기 구조 (device_info nullable) | ⚠️ Partial |

---

## Match Rate: 97%

[Plan] ✅ → [Design] ✅ → [Do] ✅ → [Check] ✅ 97% → [Report] 다음
