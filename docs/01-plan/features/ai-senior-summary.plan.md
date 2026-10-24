# Plan: AI 어르신 누적 방문기록 종합 요약

> Feature: `ai-senior-summary`
> Date: 2026-10-22
> Phase: Plan

---

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Problem** | 현재 AI 요약은 단일 방문 기록 1건만 분석하여 추이·패턴 파악 불가. 보호자와 요양사가 어르신의 건강 변화를 맥락 없이 파악해야 함. |
| **Solution** | 어르신 단위로 최근 N건(기본 10건)의 방문 기록을 누적 분석하여 추이·이상 패턴·권고사항을 AI가 종합 요약. |
| **Function UX Effect** | `POST /ai/senior-summary/{senior_id}` 호출 시 어르신의 최근 방문 기록을 시계열로 분석한 종합 요약 반환. 보호자 대시보드에서 "최근 N회 건강 요약" 형태로 노출 가능. |
| **Core Value** | 단편적 방문 데이터를 연속적 건강 스토리로 변환하여 조기 이상 징후 감지 및 케어 품질 향상. |

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| **WHY** | 요양사·보호자가 어르신의 건강 추이를 맥락 있게 파악하지 못하는 문제 해결 |
| **WHO** | 보호자(대시보드 조회), 요양사(방문 후 확인), 관리자(모니터링) |
| **RISK** | 너무 많은 기록 포함 시 Claude 토큰 비용 급증; 오래된 기록의 노이즈 가능성 |
| **SUCCESS** | senior_id 기준 누적 요약 API 정상 동작, 기존 단일 요약 API 영향 없음 |
| **SCOPE** | 신규 테이블 1개, 신규 서비스 함수 2개, 기존 API 변경 없음 |

---

## 1. 배경 및 문제 정의

### 1.1 현재 상태

```
POST /ai/summarize/{record_id}
  └── record 1건 → prompt → Claude → AiSummary (record_id FK)
```

- `AiSummary` 테이블은 `record_id`에 1:1 매핑 (unique 제약)
- 방문 기록 간 연결 없음 → 어르신의 건강 변화 추이 파악 불가
- 혈압이 3주 동안 지속 상승해도, 각 방문 요약은 독립적

### 1.2 문제점

| 문제 | 영향 |
|------|------|
| 단일 방문만 분석 | 추이·패턴 탐지 불가 |
| senior 단위 요약 없음 | 보호자 대시보드에서 종합 상태 파악 어려움 |
| 역사적 맥락 없는 이상징후 | "오늘 혈압이 높다"만 알고, "3주째 상승 중"은 모름 |

---

## 2. 요구사항

### 2.1 기능 요구사항 (FR)

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-01 | `POST /ai/senior-summary/{senior_id}` 엔드포인트 추가 | Must |
| FR-02 | 요청 파라미터 `limit` (기본값 10, 최대 30) — 최근 N건 방문 기록 포함 | Must |
| FR-03 | Claude에 시계열 순서로 방문 기록 + 활력징후 전달 | Must |
| FR-04 | 응답에 `trend_summary`, `anomaly_flags`, `recommendations` 포함 | Must |
| FR-05 | 결과를 `SeniorAiSummary` 테이블에 저장 (senior_id 기준 덮어쓰기) | Must |
| FR-06 | `GET /ai/senior-summary/{senior_id}` — 캐시된 요약 조회 | Must |
| FR-07 | 기존 `POST /ai/summarize/{record_id}` 유지 (하위 호환) | Must |
| FR-08 | 방문 기록 0건이면 404 반환 | Must |

### 2.2 비기능 요구사항 (NFR)

| ID | 요구사항 |
|----|----------|
| NFR-01 | `limit=10`일 때 API 응답 시간 < 10초 (Claude 호출 포함) |
| NFR-02 | 토큰 과다 방지: 방문 기록 1건당 최대 300자 요약하여 프롬프트 구성 |
| NFR-03 | JWT 인증 필수 (기존 패턴 동일) |

---

## 3. 설계 방향

### 3.1 데이터 모델 변경

**신규 테이블: `senior_ai_summaries`**

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer PK | |
| senior_id | Integer FK → seniors.id | unique (1 어르신 = 1 최신 요약) |
| trend_summary | Text | 전체 추이 종합 요약 (3~5문장) |
| anomaly_flags | JSON | 주목해야 할 이상 패턴 목록 |
| recommendations | JSON | 케어 제안 목록 (선택적) |
| record_count | Integer | 분석에 포함된 방문 기록 수 |
| generated_at | DateTime | 생성 시각 |
| model_used | String | 사용한 Claude 모델명 |

### 3.2 프롬프트 설계

```
[어르신 정보]
- 이름, 생년월일, 주요 특이사항

[최근 N회 방문 기록 (시간순)]
방문 1 (2026-10-01):
  - 메모 요약
  - 활력징후: 혈압 128/78, 맥박 72, ...

방문 2 (2026-10-08): ...
...

[분석 지침]
1. trend_summary: 전체 기간의 건강 추이를 3~5문장으로 요약
2. anomaly_flags: 반복되거나 악화되는 이상 패턴
3. recommendations: 보호자/요양사에게 권고할 사항

JSON 형식으로만 응답 (마크다운 없이):
{"trend_summary": "...", "anomaly_flags": [...], "recommendations": [...]}
```

### 3.3 파일 변경 계획

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `models.py` | 추가 | `SeniorAiSummary` 모델 |
| `schemas/ai_summary.py` | 추가 | `SeniorAiSummaryResponse` Pydantic 모델 |
| `services/ai_service.py` | 추가 | `generate_senior_summary()`, `get_senior_summary()` |
| `routers/ai.py` | 추가 | `POST /ai/senior-summary/{senior_id}`, `GET /ai/senior-summary/{senior_id}` |

**변경 없는 파일**: `database.py`, `auth.py`, `config.py`, 기존 라우터들

---

## 4. 엣지 케이스 및 제약

| 케이스 | 처리 방법 |
|--------|-----------|
| 방문 기록 0건 | 404 반환 |
| 방문 기록 1건 | 단일 방문 기준으로 요약 (정상 동작) |
| `limit` > 30 | 30으로 클램프 |
| Claude API 오류 | 500 반환, 기존 저장값 유지 |
| 어르신에 VitalObservation 없는 방문 | "측정값 없음"으로 프롬프트에 포함 |

---

## 5. 성공 기준

| 기준 | 검증 방법 |
|------|-----------|
| FR-01~06 API 모두 정상 동작 | 수동 테스트 (docs/visit-record-examples.md 샘플 활용) |
| 기존 `POST /ai/summarize/{record_id}` 영향 없음 | 기존 엔드포인트 호출 확인 |
| `trend_summary`에 추이 내용 포함 | 여러 방문 기록 입력 시 "지속적", "최근 N회" 같은 맥락어 확인 |
| DB에 senior_ai_summaries 레코드 저장 | DB 직접 조회 |
