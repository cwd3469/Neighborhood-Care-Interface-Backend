# CLAUDE.md

이 저장소에서 Claude Code가 작업할 때 참고하는 안내 문서.

## 프로젝트 개요

**우리 동네 시니어 케어 매니저 — 백엔드.** 방문요양 관리 API (FastAPI).
관리자·요양사·보호자 3개 역할이 어르신, 방문 일정, 방문 기록(FHIR QuestionnaireResponse),
활력징후(FHIR Observation + LOINC), Claude API 기반 AI 요약을 다룬다.

- 프론트엔드: `../web` (Next.js, Vercel 배포)
- 백엔드 배포: Render (Dockerfile, Python 3.11)
- 운영 DB: Neon PostgreSQL / 로컬·테스트 DB: SQLite

## 명령어

```bash
source venv/bin/activate
pip install -r requirements-dev.txt   # 앱 의존성 + pytest
uvicorn main:app --reload             # http://localhost:8000, 문서: /docs
pytest                                # 권한 회귀 테스트 (SQLite 인메모리, 외부 API 호출 없음)
```

## 환경변수 (.env — `.env.example` 복사)

`ANTHROPIC_API_KEY`, `SECRET_KEY`, `ALGORITHM`(HS256), `ACCESS_TOKEN_EXPIRE_MINUTES`,
`DATABASE_URL`(로컬 `sqlite:///./items.db`, 운영 Neon `postgresql://...?sslmode=require`),
`CORS_ORIGINS`(쉼표 구분).

## 구조

```
main.py        앱 생성, CORS, 라우터 등록, create_all (마이그레이션 도구 없음)
config.py      .env 로드
database.py    엔진(pool_pre_ping) + get_db
auth.py        JWT, bcrypt, refresh token(sha256 해시 저장)
models.py      User, Senior, GuardianSeniorRelation, VisitSchedule, VisitRecord,
               VitalObservation, AiSummary, SeniorAiSummary, RefreshToken
routers/       얇은 계층 — 인증·권한 검사 후 services 호출
services/      비즈니스 로직 (access_service.py = 요양사 담당 관계 정의)
schemas/       Pydantic v2 요청/응답 모델
tests/         pytest — conftest.py(고정 데이터·역할별 토큰), test_permissions.py
```

## 권한 규칙 (가장 중요 — 바꾸면 tests/test_permissions.py 함께 수정)

- 역할 의존성: `get_current_user`, `require_admin`, `require_caregiver_or_admin` (`routers/users.py`)
- 어르신 단위 접근 검사: `check_senior_access(senior_id, user, db)` — 통과 시 아무것도 안 하고, 실패 시 403
  - 보호자: `GuardianSeniorRelation`에 연결된 어르신만
  - 요양사: **B안(일정 기반)** — 그 어르신 일정이 하나라도 있으면 담당 (`services/access_service.py`)
  - 관리자: 통과
- 목록 API는 403 대신 쿼리 필터로 범위를 제한한다 (남의 id로 필터하면 빈 배열)
  - 기록 목록: 요양사는 담당 어르신 기록 전체(B2), 보호자는 연결된 어르신 기록
  - 일정 목록: 요양사는 본인 일정, 보호자는 연결된 어르신 일정
- 일정 상세·상태 변경: 요양사는 본인 일정만
- 기록 생성: 담당 어르신 + (schedule_id가 있으면) 같은 어르신 일정이어야 하고, 요양사는 본인 일정만
- `/register`는 role을 caregiver로 강제. 관리자·보호자 계정은 `POST /admin/users`로만 생성
- record_id 기반 엔드포인트는 record를 먼저 조회(없으면 404)한 뒤 `record.senior_id`로 검사
- 새 엔드포인트를 추가할 때는 위 규칙 중 어디에 해당하는지 정하고 테스트를 추가할 것

### 담당 기준을 C안(명시적 배정 테이블)으로 바꿀 때

`services/access_service.py`의 두 함수 본문만 교체하면 된다. 호출부는 그대로 둔다.

## 데이터 흐름 — 방문 기록

1. `POST /records` — FHIR QuestionnaireResponse JSON을 `visit_records.fhir_response`에 원본 저장
2. `record_service._extract_vitals` — `item.linkId`를 LOINC로 매핑해 `vital_observations`에 구조화 저장 (이중 저장)
3. `POST /ai/summarize/{record_id}` — 메모 + 활력징후로 Claude 요약 생성 → `ai_summaries`에 캐시
4. `POST /ai/senior-summary/{senior_id}` — 최근 N건 누적 분석 → `senior_ai_summaries`에 upsert

## 주의

- 테이블은 시작 시 `create_all`로 생성된다. 컬럼 변경은 운영 DB에 자동 반영되지 않는다.
- `ai_service.py`는 import 시점에 Anthropic 클라이언트를 만든다 (테스트는 conftest에서 더미 키 주입).
- `docs/`는 bkit PDCA 문서(plan → design → analysis → report).
