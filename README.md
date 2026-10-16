# 우리 동네 시니어 케어 매니저 — Backend

> 방문요양·건강기록 관리 SaaS | FHIR R5 기반 헬스케어 플랫폼

![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.129-009688?style=flat-square&logo=fastapi&logoColor=white)
![Claude API](https://img.shields.io/badge/Claude-claude--sonnet--4-D97757?style=flat-square&logo=anthropic&logoColor=white)
![FHIR](https://img.shields.io/badge/FHIR-R5-E84343?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=flat-square&logo=postgresql&logoColor=white)

---

## 프로젝트 개요

고령화 사회를 반영한 방문요양 서비스 관리 플랫폼이다.
보호자·요양사·관리자 3개 역할 기반으로 방문 일정 매칭, FHIR 표준 건강기록 저장, AI 이상징후 감지를 제공한다.

### 핵심 기능

| 기능 | 설명 |
|------|------|
| 역할 기반 접근 제어 | admin / caregiver / guardian 3개 역할, JWT 인증 |
| 방문 일정 관리 | 요양사 ↔ 어르신 매칭, 일정 상태 관리 |
| FHIR 건강기록 | 방문 기록을 QuestionnaireResponse(JSONB)로 원본 저장 |
| 활력징후 구조화 | LOINC 코드 기반 Observation 추출 → 추이 그래프용 |
| AI 요약 | 방문 메모 + 활력징후 → Claude API 요약 + 이상징후 하이라이트 |

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Framework | FastAPI 0.129 |
| AI | Anthropic Claude claude-sonnet-4-20250514 |
| 인증 | JWT (python-jose + bcrypt) |
| DB | SQLAlchemy 2.0 / SQLite (로컬) / PostgreSQL 15 (Docker) |
| 데이터 검증 | Pydantic v2 |
| FHIR 표준 | FHIR R5 QuestionnaireResponse + Observation (LOINC) |

---

## 프로젝트 구조

```
backend/
├── main.py                      # FastAPI 앱 진입점, CORS 설정
├── models.py                    # SQLAlchemy ORM 모델
├── auth.py                      # JWT 생성/검증, bcrypt 해싱
├── config.py                    # .env 환경변수 로드
├── database.py                  # DB 엔진 + 세션 의존성
├── routers/
│   ├── users.py                 # 인증, 역할 의존성 함수
│   ├── seniors.py               # 어르신 CRUD + 보호자 관계
│   ├── schedules.py             # 방문 일정 관리
│   ├── records.py               # 방문 기록 (FHIR QR)
│   ├── vitals.py                # 활력징후 추이 조회
│   └── ai.py                   # LLM 요약 + 이상징후
├── services/
│   ├── user_service.py
│   ├── senior_service.py
│   ├── schedule_service.py
│   ├── record_service.py        # FHIR QR 저장 + vital 자동 추출
│   ├── vital_service.py
│   └── ai_service.py           # Claude API 연동
└── schemas/
    ├── user.py / senior.py / schedule.py
    ├── record.py / vital.py / ai_summary.py
```

---

## 데이터 모델

```
users                  → role: admin | caregiver | guardian
seniors                → 돌봄 어르신 프로파일
guardian_senior_relations → 보호자 ↔ 어르신 N:M
visit_schedules        → 방문 일정 (caregiver ↔ senior)
visit_records          → FHIR QuestionnaireResponse (JSONB)
vital_observations     → FHIR Observation + LOINC 코드 (구조화)
ai_summaries           → LLM 요약 + 이상징후 캐시
```

### 활력징후 LOINC 코드

| 항목 | LOINC | 단위 |
|------|-------|------|
| 혈압(수축기) | 8480-6 | mmHg |
| 혈압(이완기) | 8462-4 | mmHg |
| 맥박 | 8867-4 | beats/min |
| 체온 | 8310-5 | Cel |
| 혈당 | 2339-0 | mg/dL |
| 체중 | 29463-7 | kg |
| SpO₂ | 59408-5 | % |

---

## 역할별 권한

| 엔드포인트 | admin | caregiver | guardian |
|-----------|:-----:|:---------:|:--------:|
| 어르신 등록/수정/삭제 | ✅ | - | - |
| 일정 생성/수정/삭제 | ✅ | - | - |
| 내 일정 조회 | ✅ | ✅ | - |
| 방문 기록 작성 | ✅ | ✅ | - |
| 방문 기록 조회 | ✅ | ✅(담당) | ✅(관계) |
| 활력징후 추이 | ✅ | ✅ | ✅(관계) |
| AI 요약 | ✅ | ✅ | ✅(관계) |

---

## 시작하기

### 요구사항
- Python 3.11+
- Anthropic API Key

### 설치

```bash
git clone <repo-url>
cd backend

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 환경변수 설정

```env
# .env
ANTHROPIC_API_KEY=your_anthropic_api_key
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=sqlite:///./items.db   # 로컬 개발용
```

### 서버 실행 (로컬 — SQLite)

```bash
uvicorn main:app --reload
```

API 문서: `http://localhost:8000/docs`

### DB 확인 (터미널)

```bash
sqlite3 items.db
.mode column
.headers on
SELECT * FROM users;
.quit
```

---

## Docker 배포 (PostgreSQL)

### 요구사항
- Docker
- Docker Compose

### 1. .env 설정

Docker 배포 시 `DATABASE_URL`을 PostgreSQL로 변경한다.

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=postgresql://myuser:mypassword@db:5432/mydb
```

> **주의**: `db`는 docker-compose 내부 서비스 이름이므로 로컬 직접 실행 시에는 동작하지 않는다.
> 로컬 개발에는 `DATABASE_URL=sqlite:///./items.db` 를 사용할 것.

### 2. 빌드 및 실행

```bash
# 처음 실행 or 코드 변경 후
docker-compose up --build

# 백그라운드 실행
docker-compose up -d --build
```

### 3. 서비스 구성

| 서비스 | 이미지 | 포트 | 설명 |
|--------|--------|------|------|
| `app` | 로컬 Dockerfile 빌드 | 8000 | FastAPI 서버 |
| `db` | postgres:15 | 5432 | PostgreSQL DB |

### 4. 주요 명령어

```bash
# 컨테이너 중지
docker-compose down

# 컨테이너 중지 + 볼륨(DB 데이터) 삭제
docker-compose down -v

# 로그 확인
docker-compose logs -f app

# DB 접속
docker-compose exec db psql -U myuser -d mydb
\dt          -- 테이블 목록
SELECT * FROM users;
\q
```

### 5. 데이터 영속성

PostgreSQL 데이터는 `postgres_data` named volume에 저장된다.
`docker-compose down` 만으로는 데이터가 삭제되지 않으며, `-v` 옵션을 붙여야 삭제된다.

---

## API 엔드포인트

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| POST | `/register` | - | 회원가입 (role 포함) |
| POST | `/login` | - | 로그인 → JWT 발급 |
| GET | `/me` | 인증 | 내 정보 |
| GET | `/admin/users` | admin | 전체 유저 목록 |
| GET | `/seniors` | 인증 | 어르신 목록 (역할별 필터) |
| POST | `/seniors` | admin | 어르신 등록 |
| POST | `/seniors/{id}/guardians` | admin | 보호자 관계 등록 |
| GET | `/schedules` | 인증 | 방문 일정 목록 |
| POST | `/schedules` | admin | 일정 생성 |
| PATCH | `/schedules/{id}/status` | 인증 | 일정 상태 변경 |
| GET | `/records` | 인증 | 방문 기록 목록 |
| POST | `/records` | caregiver/admin | 방문 기록 작성 |
| GET | `/records/{id}/vitals` | 인증 | 기록별 활력징후 |
| GET | `/vitals/seniors/{id}` | 인증 | 어르신 활력징후 추이 |
| POST | `/ai/summarize/{id}` | 인증 | AI 요약 생성 |
| GET | `/ai/summary/{id}` | 인증 | AI 요약 조회 |
