# Report: user-refresh-token — Refresh Token 만료 및 갱신 관리

**작성일**: 2026-09-25
**Phase**: Completed
**Match Rate**: 97%
**성공 기준 달성률**: 5/5 (100%)

---

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | user-refresh-token |
| **기간** | 2026-09-25 (단일 세션) |
| **Match Rate** | 97% |
| **변경 파일** | 4개 수정 + 2개 신규 |

### Value Delivered

| 관점 | 내용 |
|------|------|
| **Problem** | Access Token(30분) 만료 시 재로그인으로 요양사·보호자 현장 업무 단절 |
| **Solution** | Refresh Token(7일) DB 저장 + `/auth/refresh` + `/auth/logout` API 제공 |
| **Function UX Effect** | 로그인 빈도 대폭 감소, 현장 앱 세션 자동 유지, 로그아웃 즉시 무효화 |
| **Core Value** | 돌봄 현장에서 중단 없는 서비스 연속성 — 방문 기록·활력징후 입력 중 데이터 손실 방지 |

---

## 1. 구현 결과

### 1.1 변경된 파일

| 파일 | 변경 유형 | 주요 내용 |
|------|-----------|-----------|
| `models.py` | 수정 | `RefreshToken` 모델 추가 (refresh_tokens 테이블) |
| `auth.py` | 수정 | `create_refresh_token`, `hash_refresh_token`, `verify_refresh_token` 추가 |
| `schemas/user.py` | 수정 | `Token`에 `refresh_token` 필드 추가, `RefreshRequest/Response/LogoutRequest` 신규 |
| `services/user_service.py` | 수정 | `login_user` — refresh token 발급·DB 저장 로직 추가 |
| `services/auth_service.py` | **신규** | refresh/logout 비즈니스 로직 |
| `routers/auth.py` | **신규** | `POST /auth/refresh`, `POST /auth/logout` 엔드포인트 |
| `main.py` | 수정 | auth 라우터 등록 |

### 1.2 신규 API

| Method | Path | 설명 |
|--------|------|------|
| POST | `/login` | 기존 + `refresh_token` 응답 추가 |
| POST | `/auth/refresh` | Refresh Token → 새 Access Token |
| POST | `/auth/logout` | Refresh Token 무효화 (멱등성 보장) |

### 1.3 DB 변경

```sql
-- 자동 생성 (create_all)
CREATE TABLE refresh_tokens (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR NOT NULL,       -- bcrypt 해시
    expires_at  DATETIME NOT NULL,
    created_at  DATETIME DEFAULT NOW(),
    device_info VARCHAR               -- nullable, 추후 다중기기 식별용
);
CREATE INDEX ix_refresh_tokens_token_hash ON refresh_tokens(token_hash);
```

---

## 2. 성공 기준 최종 상태

| ID | 기준 | 최종 상태 | 근거 |
|----|------|-----------|------|
| SC-01 | `/login` 응답에 `refresh_token` 포함 | ✅ Met | `user_service.py:50` — `"refresh_token": raw_refresh` |
| SC-02 | 유효한 refresh_token → 새 access_token | ✅ Met | `auth_service.py:19-33` — `POST /auth/refresh` |
| SC-03 | 로그아웃 후 갱신 → 401 | ✅ Met | DB 삭제 후 `_find_matching_token` 실패 → 401 |
| SC-04 | 만료된 refresh_token → 401 | ✅ Met | `expires_at > now` 필터로 자동 제외 |
| SC-05 | 기존 응답 필드 유지 | ✅ Met | `access_token`, `token_type`, `role` 기존 유지 |

**성공 기준 달성률: 5/5 (100%)**

---

## 3. Key Decisions & Outcomes

| 단계 | 결정 | 결과 |
|------|------|------|
| **Plan** | Refresh Token → DB 별도 테이블 저장 | ✅ 다중 기기 지원 구조 확보, CASCADE 삭제 자동화 |
| **Plan** | 만료 7일 | ✅ `REFRESH_TOKEN_EXPIRE_DAYS = 7` 상수화 |
| **Plan** | 로그아웃 = DB 삭제만 (Access Token 블랙리스트 없음) | ✅ 멱등성 보장, 구현 단순화 |
| **Design** | Option C (실용적 균형) — 기존 코드 최소 수정 | ✅ 기존 라우터 무수정, 신규 2파일만 추가 |
| **Design** | bcrypt로 해시만 DB 저장 | ✅ 원문 미저장 보안 원칙 준수 |
| **Design** | 멱등성 로그아웃 | ✅ 토큰 없어도 200 반환 — 클라이언트 오류 방지 |
| **Check** | `auth_service.py` expires_delta 하드코딩 수정 | ✅ config `ACCESS_TOKEN_EXPIRE_MINUTES` 자동 적용 |

---

## 4. Gap 처리 결과

| Gap | 심각도 | 처리 |
|-----|--------|------|
| auth_service.py 30분 하드코딩 | Important | ✅ 수정 완료 — expires_delta 제거, config 값 자동 적용 |
| device_info 미저장 | Minor | 허용 — nullable 필드, 추후 확장 가능 |

---

## 5. 보안 구현 현황

| 원칙 | 구현 상태 |
|------|-----------|
| 원문 DB 미저장 | ✅ bcrypt 해시만 저장 |
| 만료 강제 | ✅ DB 레벨 `expires_at` 검사 |
| 로그아웃 즉시 무효화 | ✅ DB 행 삭제 |
| 유저 삭제 시 자동 정리 | ✅ `ON DELETE CASCADE` |
| HTTPS | 배포 시 필수 (앱 레벨 보장 불가) |

---

## 6. 프론트 연동 가이드 (최종)

```
1. POST /login → { access_token, refresh_token, token_type, role }
   → refresh_token을 HttpOnly Cookie 또는 SecureStorage에 저장

2. API 호출 시 access_token 사용 (Authorization: Bearer {access_token})
   → 401 응답 수신 시:
     POST /auth/refresh { refresh_token }
     → 새 access_token 저장 후 원래 요청 재시도

3. 로그아웃 시:
   POST /auth/logout { refresh_token }
   → 클라이언트 저장소 초기화
```

---

## 7. 향후 개선 제안

| 항목 | 설명 | 우선순위 |
|------|------|----------|
| Refresh Token Rotation | 갱신 시 새 refresh_token도 발급 — 탈취 감지 가능 | Should |
| device_info 저장 | 로그인 시 User-Agent 저장 → 기기 목록 관리 | Could |
| 만료 토큰 주기적 정리 | APScheduler로 DB 용량 관리 | Could |

---

## 8. PDCA 사이클 요약

```
[Plan] ✅ 2026-09-25  →  [Design] ✅ 2026-09-25
  ↓
[Do] ✅ 2026-09-25 (M1~M7, ~140줄)
  ↓
[Check] ✅ 97% → Important 1건 수정
  ↓
[Report] ✅ 완료
```
