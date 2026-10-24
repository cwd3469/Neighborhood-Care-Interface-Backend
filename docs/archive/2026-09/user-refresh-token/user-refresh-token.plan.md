# Plan: user-refresh-token — Refresh Token 만료 및 갱신 관리

**작성일**: 2026-09-25
**Phase**: Plan
**Feature ID**: user-refresh-token

---

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Problem** | Access Token(30분) 만료 시 재로그인 필요 — 사용자 경험 단절, 특히 요양사/보호자의 현장 업무 흐름 방해 |
| **Solution** | Refresh Token(7일) 발급 + DB 저장 + 갱신 API 제공 — 자동 토큰 갱신으로 세션 지속 |
| **Function UX Effect** | 로그인 빈도 감소, 현장에서 앱이 갑자기 튕기지 않음, 다중 기기 로그인 관리 가능 |
| **Core Value** | 의료/돌봄 현장에서 중단 없는 서비스 연속성 보장 |

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| **WHY** | 요양사/보호자가 현장 업무 중 세션 만료로 업무가 끊기는 문제 해결 |
| **WHO** | 요양사(caregiver), 보호자(guardian), 관리자(admin) — 모든 역할 |
| **RISK** | Refresh Token 탈취 시 7일간 계정 접근 가능 → rotation 고려, HTTPS 필수 |
| **SUCCESS** | 로그인 후 7일간 재로그인 없이 서비스 이용 가능, 로그아웃 시 즉시 무효화 |
| **SCOPE** | 백엔드만 (FastAPI) — 프론트 연동 가이드 포함, 프론트 코드 수정 제외 |

---

## 1. 현재 상태 분석

### 1.1 현재 인증 흐름
```
POST /login → Access Token (30분) 발급 → 만료 시 재로그인
```

### 1.2 문제점
- Access Token 만료 시 자동 갱신 수단 없음
- 모든 역할(admin/caregiver/guardian)이 동일한 문제 경험
- 현장 업무(방문 기록, 활력징후 입력) 중 세션 만료 시 입력 데이터 손실 위험

### 1.3 관련 파일
| 파일 | 역할 |
|------|------|
| `auth.py` | JWT 생성/검증 — `create_access_token`, `decode_access_token` |
| `models.py` | SQLAlchemy ORM — `User` 모델 (refresh token 없음) |
| `routers/users.py` | `/login`, `/register`, `/me` 엔드포인트 |
| `schemas/user.py` | `Token` 스키마 (access_token, token_type, role) |
| `services/user_service.py` | `login_user` — 현재 access token만 반환 |

---

## 2. 요구사항

### 2.1 기능 요구사항

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-01 | 로그인 시 Access Token(30분) + Refresh Token(7일) 동시 발급 | Must |
| FR-02 | `POST /auth/refresh` — Refresh Token으로 새 Access Token 발급 | Must |
| FR-03 | `POST /auth/logout` — Refresh Token DB에서 삭제(무효화) | Must |
| FR-04 | Refresh Token은 DB(`refresh_tokens` 테이블)에 해시값 저장 | Must |
| FR-05 | 만료된 Refresh Token 요청 시 401 반환 | Must |
| FR-06 | 다중 기기 지원 — 기기별 독립적 Refresh Token | Should |

### 2.2 비기능 요구사항

| ID | 요구사항 |
|----|----------|
| NFR-01 | Refresh Token 원문은 클라이언트에만 저장, DB에는 bcrypt 해시 저장 |
| NFR-02 | 만료 토큰 자동 정리 (created_at + 7일 기준 스케줄 or 요청 시점 정리) |
| NFR-03 | 기존 `/login` 응답 스키마 하위 호환 유지 (`access_token`, `token_type`, `role` 유지) |
| NFR-04 | SQLite(로컬) / PostgreSQL(Docker) 모두 동작 |

---

## 3. 설계 방향 (High-level)

### 3.1 신규 DB 테이블: `refresh_tokens`

```
refresh_tokens
├── id          (PK)
├── user_id     (FK → users.id)
├── token_hash  (String, hashed refresh token)
├── expires_at  (DateTime)
├── created_at  (DateTime)
└── device_info (String, nullable — user-agent 등)
```

### 3.2 신규/변경 API

| Method | Path | 설명 |
|--------|------|------|
| POST | `/login` | 기존 유지 + refresh_token 응답 추가 |
| POST | `/auth/refresh` | Refresh Token → 새 Access Token |
| POST | `/auth/logout` | Refresh Token 무효화 |

### 3.3 토큰 흐름

```
[로그인]
  POST /login
    → access_token (JWT, 30분)
    → refresh_token (opaque token, 7일, DB 저장)

[갱신]
  POST /auth/refresh { refresh_token }
    → 검증 (DB 조회 + 만료 확인)
    → 새 access_token 반환
    (Refresh Token Rotation 옵션: 새 refresh_token도 발급)

[로그아웃]
  POST /auth/logout { refresh_token }
    → DB에서 해당 refresh_token 삭제
```

---

## 4. 구현 범위

### 4.1 수정 파일
| 파일 | 변경 내용 |
|------|-----------|
| `models.py` | `RefreshToken` 모델 추가 |
| `auth.py` | `create_refresh_token`, `verify_refresh_token` 함수 추가 |
| `schemas/user.py` | `Token` 스키마에 `refresh_token` 필드 추가 |
| `services/user_service.py` | `login_user` — refresh token 발급 로직 추가 |

### 4.2 신규 파일
| 파일 | 내용 |
|------|------|
| `routers/auth.py` | `/auth/refresh`, `/auth/logout` 엔드포인트 |
| `services/auth_service.py` | refresh/logout 비즈니스 로직 |

### 4.3 main.py
- `auth` 라우터 등록 추가

---

## 5. 성공 기준

| ID | 기준 | 검증 방법 |
|----|------|-----------|
| SC-01 | 로그인 응답에 `refresh_token` 포함 | `/login` 응답 확인 |
| SC-02 | 만료된 access token + 유효한 refresh token → 새 access token 발급 | `/auth/refresh` 테스트 |
| SC-03 | 로그아웃 후 해당 refresh token으로 갱신 불가 (401) | 로그아웃 후 `/auth/refresh` 시도 |
| SC-04 | 만료된 refresh token 요청 시 401 반환 | 만료 토큰으로 테스트 |
| SC-05 | 기존 `/login` 응답의 `access_token`, `token_type`, `role` 유지 | 프론트 호환성 확인 |

---

## 6. 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| Refresh Token 탈취 | 7일간 계정 접근 가능 | HTTPS 필수, 추후 Token Rotation 도입 고려 |
| DB 토큰 테이블 증가 | 성능 저하 | 만료 토큰 주기적 정리 (NFR-02) |
| 기존 프론트 호환성 | 응답 스키마 변경 시 에러 | `refresh_token` 필드만 추가 (기존 필드 유지) |

---

## 7. 프론트 연동 가이드

로그인 후 `refresh_token`을 안전한 저장소(HttpOnly Cookie 권장, 또는 SecureStorage)에 저장.
Access Token 만료(401) 수신 시 자동으로 `POST /auth/refresh` 호출하여 갱신.
로그아웃 시 `POST /auth/logout`으로 서버 측 토큰 삭제 후 클라이언트 저장소 초기화.

---

## 8. 다음 단계

```
/pdca design user-refresh-token
```
