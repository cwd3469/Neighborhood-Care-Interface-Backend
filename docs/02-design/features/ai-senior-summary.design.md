# Design: AI 어르신 누적 방문기록 종합 요약

> Feature: `ai-senior-summary`
> Date: 2026-10-22
> Phase: Design
> Architecture: Option A — 최소 변경

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| **WHY** | 요양사·보호자가 어르신의 건강 추이를 맥락 있게 파악하지 못하는 문제 해결 |
| **WHO** | 보호자(대시보드 조회), 요양사(방문 후 확인), 관리자(모니터링) |
| **RISK** | 너무 많은 기록 포함 시 Claude 토큰 비용 급증; 오래된 기록의 노이즈 가능성 |
| **SUCCESS** | senior_id 기준 누적 요약 API 정상 동작, 기존 단일 요약 API 영향 없음 |
| **SCOPE** | 신규 테이블 1개, 기존 파일 4개 수정, 신규 파일 없음 |

---

## 1. 아키텍처 개요

### 1.1 선택 근거

Option A(최소 변경)를 선택. 기존 `ai_service.py`에 이미 `MODEL`, `_client`, `NORMAL_RANGES`가 정의되어 있고, 누적 요약 로직도 동일한 상수를 활용한다. 현재 코드베이스 규모에서 파일 분리보다 응집력 유지가 실용적이다.

### 1.2 데이터 흐름

```
POST /ai/senior-summary/{senior_id}?limit=10
  │
  ▼
routers/ai.py: generate_senior_summary_route()
  │
  ▼
services/ai_service.py: generate_senior_summary(senior_id, limit, db)
  ├── DB 조회: VisitRecord (senior_id, 최근 limit건, recorded_at DESC)
  ├── DB 조회: VitalObservation (record_id IN [...])
  ├── Senior 정보 조회 (이름, 생년월일, medical_notes)
  ├── _build_senior_prompt() 호출
  ├── Claude API 호출 (claude-sonnet-4-20250514)
  ├── JSON 파싱 (trend_summary, anomaly_flags, recommendations)
  └── SeniorAiSummary upsert (senior_id unique — 덮어쓰기)
  │
  ▼
SeniorAiSummaryResponse 반환
```

---

## 2. 데이터 모델

### 2.1 신규 테이블: `senior_ai_summaries`

```python
class SeniorAiSummary(Base):
    __tablename__ = "senior_ai_summaries"

    id            = Column(Integer, primary_key=True, index=True)
    senior_id     = Column(Integer, ForeignKey("seniors.id"), unique=True, nullable=False)
    trend_summary = Column(Text, nullable=False)
    anomaly_flags = Column(JSON, nullable=True)    # list[str]
    recommendations = Column(JSON, nullable=True)  # list[str]
    record_count  = Column(Integer, nullable=False) # 분석에 포함된 방문 수
    generated_at  = Column(DateTime, default=datetime.utcnow)
    model_used    = Column(String, nullable=False)
```

**`senior_id` unique 제약**: 1 어르신 = 1 최신 요약. 호출마다 덮어쓰기(upsert).

### 2.2 기존 테이블 변경 없음

`AiSummary`, `VisitRecord`, `VitalObservation`, `Senior` — 변경 없음.

---

## 3. API 설계

### 3.1 POST /ai/senior-summary/{senior_id}

**Request**

```
POST /ai/senior-summary/42?limit=10
Authorization: Bearer <JWT>
```

| 파라미터 | 위치 | 타입 | 기본값 | 제약 |
|---------|------|------|--------|------|
| `senior_id` | path | int | — | 필수 |
| `limit` | query | int | 10 | 1~30 (초과 시 30으로 클램프) |

**Response: 200 OK**

```json
{
  "id": 1,
  "senior_id": 42,
  "trend_summary": "최근 10회 방문 동안 혈압이 완만한 상승 추세를 보이고 있습니다...",
  "anomaly_flags": ["혈압 수축기 3회 연속 140 초과", "식사량 지속 감소"],
  "recommendations": ["혈압약 복용 여부 재확인 권장", "보호자에게 식욕 저하 공유 필요"],
  "record_count": 10,
  "generated_at": "2026-10-22T10:00:00",
  "model_used": "claude-sonnet-4-20250514"
}
```

**Error Cases**

| 상황 | 상태코드 | detail |
|------|----------|--------|
| senior_id 없음 | 404 | "어르신을 찾을 수 없습니다" |
| 방문 기록 0건 | 404 | "방문 기록이 없습니다" |
| Claude API 오류 | 500 | "AI 요약 생성 실패" |

### 3.2 GET /ai/senior-summary/{senior_id}

**Request**

```
GET /ai/senior-summary/42
Authorization: Bearer <JWT>
```

**Response: 200 OK** — `SeniorAiSummaryResponse` (위와 동일 구조)

**Error**

| 상황 | 상태코드 | detail |
|------|----------|--------|
| 요약 없음 | 404 | "아직 생성된 요약이 없습니다. POST /ai/senior-summary/{senior_id} 를 먼저 호출하세요." |

---

## 4. 프롬프트 설계

### 4.1 `_build_senior_prompt()` 함수

```python
def _build_senior_prompt(senior: Senior, records_with_vitals: list[tuple]) -> str:
    """
    records_with_vitals: [(VisitRecord, list[VitalObservation]), ...]
    시간 오름차순 정렬 (가장 오래된 것부터)
    """
```

**프롬프트 구조**

```
다음은 [어르신 이름]님의 최근 N회 방문 기록입니다. 시계열 순서로 건강 추이를 분석하고 JSON 형식으로만 응답하세요.

[어르신 정보]
- 이름: 홍길동
- 생년월일: 1940-05-15
- 특이사항: 고혈압, 당뇨

[방문 기록 (오래된 순)]

방문 1 (2026-09-01):
  메모: 아침 식사 정상 섭취, 복약 완료. 특이사항 없음.
  활력징후:
  - 혈압(수축기): 132 mmHg (정상: 90~140)
  - 혈압(이완기): 82 mmHg (정상: 60~90)
  - 맥박: 74 beats/min (정상: 60~100)

방문 2 (2026-09-08):
  메모: ...
  활력징후: ...

...

[분석 지침]
1. trend_summary: 전체 기간의 건강 추이를 3~5문장으로 요약. 수치 변화 패턴, 반복 증상, 개선/악화 여부 포함.
2. anomaly_flags: 반복되거나 악화되는 이상 패턴 목록 (없으면 빈 배열).
3. recommendations: 보호자/요양사에게 권고할 사항 목록 (없으면 빈 배열).

응답 형식 (JSON만, 마크다운 없이):
{"trend_summary": "...", "anomaly_flags": [...], "recommendations": [...]}
```

### 4.2 토큰 최적화

- 방문 기록 1건당 메모는 `visit_notes[:200]` (200자 잘라내기)로 제한
- 정상범위 정보는 `NORMAL_RANGES` 그대로 활용 (기존 로직 재사용)
- `limit=10`, 건당 ~200자 → 예상 입력 토큰: ~1,500~2,000

---

## 5. 파일별 변경 명세

### 5.1 `models.py`

```python
# 기존 코드 아래에 추가
class SeniorAiSummary(Base):
    __tablename__ = "senior_ai_summaries"

    id              = Column(Integer, primary_key=True, index=True)
    senior_id       = Column(Integer, ForeignKey("seniors.id"), unique=True, nullable=False)
    trend_summary   = Column(Text, nullable=False)
    anomaly_flags   = Column(JSON, nullable=True)
    recommendations = Column(JSON, nullable=True)
    record_count    = Column(Integer, nullable=False)
    generated_at    = Column(DateTime, default=datetime.utcnow)
    model_used      = Column(String, nullable=False)
```

`main.py`의 `Base.metadata.create_all()` 호출 시 자동 생성됨 — 별도 마이그레이션 불필요.

### 5.2 `schemas/ai_summary.py`

```python
# 기존 AiSummaryResponse 유지, 아래에 추가
class SeniorAiSummaryResponse(BaseModel):
    id: int
    senior_id: int
    trend_summary: str
    anomaly_flags: Optional[list[str]] = None
    recommendations: Optional[list[str]] = None
    record_count: int
    generated_at: datetime
    model_used: str

    class Config:
        from_attributes = True
```

### 5.3 `services/ai_service.py`

추가할 함수 2개:

```python
def _build_senior_prompt(senior, records_with_vitals: list) -> str:
    # 시계열 프롬프트 구성 (§4.1 참조)

def generate_senior_summary(senior_id: int, limit: int, db: Session) -> SeniorAiSummary:
    # 1. Senior 조회 (없으면 404)
    # 2. VisitRecord 최근 limit건 조회 (recorded_at DESC, 정렬 후 역순으로 프롬프트 구성)
    # 3. 각 record의 VitalObservation 일괄 조회
    # 4. _build_senior_prompt() 호출
    # 5. Claude API 호출 (max_tokens=1024)
    # 6. JSON 파싱
    # 7. SeniorAiSummary upsert

def get_senior_summary(senior_id: int, db: Session) -> SeniorAiSummary:
    # senior_ai_summaries에서 senior_id로 조회, 없으면 404
```

**upsert 패턴** (기존 `generate_summary`와 동일):
```python
existing = db.query(SeniorAiSummary).filter(SeniorAiSummary.senior_id == senior_id).first()
if existing:
    existing.trend_summary = ...
    existing.anomaly_flags = ...
    # ... 나머지 필드 갱신
    db.commit(); db.refresh(existing); return existing

obj = SeniorAiSummary(...)
db.add(obj); db.commit(); db.refresh(obj); return obj
```

### 5.4 `routers/ai.py`

```python
from schemas.ai_summary import AiSummaryResponse, SeniorAiSummaryResponse
from services.ai_service import generate_summary, get_summary, generate_senior_summary, get_senior_summary

@router.post("/senior-summary/{senior_id}", response_model=SeniorAiSummaryResponse)
def summarize_senior(
    senior_id: int,
    limit: int = Query(default=10, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """어르신의 최근 N건 방문 기록을 누적 분석하여 종합 요약을 생성합니다."""
    return generate_senior_summary(senior_id, limit, db)


@router.get("/senior-summary/{senior_id}", response_model=SeniorAiSummaryResponse)
def get_cached_senior_summary(
    senior_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """캐시된 어르신 종합 요약 조회."""
    return get_senior_summary(senior_id, db)
```

---

## 6. 엣지 케이스 처리

| 케이스 | 처리 |
|--------|------|
| `limit` > 30 | `Query(le=30)` FastAPI 자동 422 반환 |
| 방문 기록 0건 | `generate_senior_summary` 내부에서 404 raise |
| 방문 기록 1건 | 단일 방문 기준으로 정상 요약 생성 |
| VitalObservation 없는 방문 | 프롬프트에 "측정값 없음" 삽입 |
| Claude API 오류 | 예외 전파 → FastAPI 500 자동 변환 |
| `senior_id` DB에 없음 | Senior 조회 시 404 raise |

---

## 7. 구현 순서

```
1. models.py         — SeniorAiSummary 클래스 추가
2. schemas/ai_summary.py — SeniorAiSummaryResponse 추가
3. services/ai_service.py — _build_senior_prompt(), generate_senior_summary(), get_senior_summary() 추가
4. routers/ai.py     — 엔드포인트 2개 추가 + import 갱신
5. 수동 테스트       — POST → GET 흐름, limit 파라미터, 엣지 케이스
```

---

## 8. 테스트 시나리오

| # | 시나리오 | 기대 결과 |
|---|----------|-----------|
| T1 | 방문 기록 10건 있는 어르신 → `POST /ai/senior-summary/{id}` | 200, `trend_summary` 비어있지 않음 |
| T2 | 동일 어르신 재호출 | 200, `generated_at` 갱신, `id` 동일 (upsert) |
| T3 | `GET /ai/senior-summary/{id}` | 200, T1과 동일 데이터 |
| T4 | 방문 기록 0건 어르신 | 404 |
| T5 | `limit=5` | `record_count=5` |
| T6 | `limit=50` | FastAPI 422 (le=30 위반) |
| T7 | 기존 `POST /ai/summarize/{record_id}` | 200, 동작 변화 없음 |
| T8 | 존재하지 않는 `senior_id` | 404 |

---

## 11. Implementation Guide

### 11.1 구현 전 체크리스트

- [ ] `models.py`에서 `datetime` import 확인 (이미 있음)
- [ ] `schemas/ai_summary.py`에서 `Optional`, `list` import 확인
- [ ] `routers/ai.py`에서 `Query` import 추가 필요 (`from fastapi import APIRouter, Depends, Query`)

### 11.2 주의사항

- `SeniorAiSummary`를 `models.py`에 추가하면 앱 재시작 시 `Base.metadata.create_all()`이 자동으로 테이블 생성함 (SQLite/PostgreSQL 모두)
- `VitalObservation` 일괄 조회: record_id 목록으로 IN 쿼리 사용하여 N+1 쿼리 방지
- `max_tokens=1024` 설정 (단일 요약의 512에서 상향)

### 11.3 Session Guide

**Module Map**

| 모듈 | 파일 | 예상 작업 |
|------|------|-----------|
| M1-model | `models.py` | `SeniorAiSummary` 클래스 추가 (~15줄) |
| M2-schema | `schemas/ai_summary.py` | `SeniorAiSummaryResponse` 추가 (~12줄) |
| M3-service | `services/ai_service.py` | 함수 3개 추가 (~70줄) |
| M4-router | `routers/ai.py` | 엔드포인트 2개 + import 갱신 (~20줄) |

**권장 세션 계획**

모든 모듈이 단순하므로 단일 세션에서 M1→M2→M3→M4 순서로 완료 권장.
