import json
import anthropic
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import VisitRecord, VitalObservation, AiSummary, Senior, SeniorAiSummary

MODEL = "claude-sonnet-4-20250514"

# 활력징후 정상 범위 (AI 프롬프트 참고용)
NORMAL_RANGES = {
    "8480-6":  ("혈압(수축기)",  90,  140, "mmHg"),
    "8462-4":  ("혈압(이완기)",  60,   90, "mmHg"),
    "8867-4":  ("맥박",          60,  100, "beats/min"),
    "8310-5":  ("체온",         36.0, 37.5, "°C"),
    "2339-0":  ("혈당",          70,  100, "mg/dL"),
    "59408-5": ("SpO₂",          95,  100, "%"),
}

_client = anthropic.Anthropic()


def _build_prompt(record: VisitRecord, vitals: list[VitalObservation]) -> str:
    vital_lines = []
    for v in vitals:
        range_info = NORMAL_RANGES.get(v.loinc_code)
        if range_info:
            _, lo, hi, unit = range_info
            flag = " ⚠️ 범위 초과" if not (lo <= v.value <= hi) else ""
            vital_lines.append(f"- {v.display_name}: {v.value} {v.unit} (정상: {lo}~{hi}){flag}")
        else:
            vital_lines.append(f"- {v.display_name}: {v.value} {v.unit}")

    vitals_text = "\n".join(vital_lines) if vital_lines else "측정값 없음"
    notes_text = record.visit_notes or "특이사항 없음"

    return f"""다음은 방문요양 기록입니다. 아래 지침에 따라 JSON 형식으로만 응답하세요.

[방문 메모]
{notes_text}

[측정된 활력징후]
{vitals_text}

응답 형식 (JSON만, 마크다운 없이):
{{
  "summary": "방문 내용을 2-3문장으로 한국어 요약",
  "anomaly_flags": ["이상징후 항목1", "이상징후 항목2"]
}}

anomaly_flags는 정상 범위를 벗어난 수치나 메모에서 발견된 이상증상 목록입니다. 없으면 빈 배열 []."""


def generate_summary(record_id: int, db: Session) -> AiSummary:
    record = db.query(VisitRecord).filter(VisitRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="방문 기록을 찾을 수 없습니다")

    vitals = db.query(VitalObservation).filter(VitalObservation.record_id == record_id).all()

    prompt = _build_prompt(record, vitals)

    message = _client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()

    try:
        parsed = json.loads(raw)
        summary_text = parsed.get("summary", raw)
        anomaly_flags = parsed.get("anomaly_flags", [])
    except json.JSONDecodeError:
        summary_text = raw
        anomaly_flags = []

    # 기존 요약 있으면 덮어쓰기
    existing = db.query(AiSummary).filter(AiSummary.record_id == record_id).first()
    if existing:
        existing.summary = summary_text
        existing.anomaly_flags = anomaly_flags
        existing.generated_at = datetime.utcnow()
        existing.model_used = MODEL
        db.commit()
        db.refresh(existing)
        return existing

    ai_summary = AiSummary(
        record_id=record_id,
        summary=summary_text,
        anomaly_flags=anomaly_flags,
        model_used=MODEL,
    )
    db.add(ai_summary)
    db.commit()
    db.refresh(ai_summary)
    return ai_summary


def get_summary(record_id: int, db: Session) -> AiSummary:
    summary = db.query(AiSummary).filter(AiSummary.record_id == record_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="아직 생성된 요약이 없습니다. POST /ai/summarize/{record_id} 를 먼저 호출하세요.")
    return summary


# Design Ref: §4.1 — 시계열 프롬프트, 방문 1건당 메모 200자 잘라내기로 토큰 최적화
def _build_senior_prompt(senior: Senior, records_with_vitals: list) -> str:
    """
    records_with_vitals: [(VisitRecord, list[VitalObservation]), ...]
    오래된 순(시간 오름차순)으로 전달된다고 가정
    """
    senior_info = (
        f"이름: {senior.full_name}\n"
        f"생년월일: {senior.birth_date}\n"
        f"특이사항: {senior.medical_notes or '없음'}"
    )

    visit_blocks = []
    for i, (record, vitals) in enumerate(records_with_vitals, 1):
        date_str = record.recorded_at.strftime("%Y-%m-%d") if record.recorded_at else "날짜 미상"
        notes = (record.visit_notes or "특이사항 없음")[:200]

        vital_lines = []
        for v in vitals:
            range_info = NORMAL_RANGES.get(v.loinc_code)
            if range_info:
                _, lo, hi, unit = range_info
                flag = " ⚠️" if not (lo <= v.value <= hi) else ""
                vital_lines.append(f"  - {v.display_name}: {v.value} {v.unit} (정상: {lo}~{hi}){flag}")
            else:
                vital_lines.append(f"  - {v.display_name}: {v.value} {v.unit}")

        vitals_text = "\n".join(vital_lines) if vital_lines else "  측정값 없음"
        visit_blocks.append(
            f"방문 {i} ({date_str}):\n  메모: {notes}\n  활력징후:\n{vitals_text}"
        )

    visits_text = "\n\n".join(visit_blocks)

    return f"""다음은 [{senior.full_name}]님의 최근 {len(records_with_vitals)}회 방문 기록입니다. 시계열 순서로 건강 추이를 분석하고 JSON 형식으로만 응답하세요.

[어르신 정보]
{senior_info}

[방문 기록 (오래된 순)]

{visits_text}

[분석 지침]
1. trend_summary: 전체 기간의 건강 추이를 3~5문장으로 요약. 수치 변화 패턴, 반복 증상, 개선/악화 여부 포함.
2. anomaly_flags: 반복되거나 악화되는 이상 패턴 목록. 없으면 빈 배열.
3. recommendations: 보호자/요양사에게 권고할 사항 목록. 없으면 빈 배열.

응답 형식 (JSON만, 마크다운 없이):
{{"trend_summary": "...", "anomaly_flags": [...], "recommendations": [...]}}"""


# Plan SC: FR-01, FR-02, FR-03, FR-04, FR-05 — 누적 요약 생성 및 upsert
def generate_senior_summary(senior_id: int, limit: int, db: Session) -> SeniorAiSummary:
    senior = db.query(Senior).filter(Senior.id == senior_id).first()
    if not senior:
        raise HTTPException(status_code=404, detail="어르신을 찾을 수 없습니다")

    records = (
        db.query(VisitRecord)
        .filter(VisitRecord.senior_id == senior_id)
        .order_by(VisitRecord.recorded_at.desc())
        .limit(limit)
        .all()
    )
    if not records:
        raise HTTPException(status_code=404, detail="방문 기록이 없습니다")

    # N+1 방지: record_id 목록으로 일괄 조회
    record_ids = [r.id for r in records]
    all_vitals = (
        db.query(VitalObservation)
        .filter(VitalObservation.record_id.in_(record_ids))
        .all()
    )
    vitals_by_record = {}
    for v in all_vitals:
        vitals_by_record.setdefault(v.record_id, []).append(v)

    # 오래된 순 정렬 (프롬프트는 시간 오름차순)
    records_asc = list(reversed(records))
    records_with_vitals = [(r, vitals_by_record.get(r.id, [])) for r in records_asc]

    prompt = _build_senior_prompt(senior, records_with_vitals)

    message = _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()

    try:
        parsed = json.loads(raw)
        trend_summary = parsed.get("trend_summary", raw)
        anomaly_flags = parsed.get("anomaly_flags", [])
        recommendations = parsed.get("recommendations", [])
    except json.JSONDecodeError:
        trend_summary = raw
        anomaly_flags = []
        recommendations = []

    # upsert: senior_id 기준 덮어쓰기
    existing = db.query(SeniorAiSummary).filter(SeniorAiSummary.senior_id == senior_id).first()
    if existing:
        existing.trend_summary = trend_summary
        existing.anomaly_flags = anomaly_flags
        existing.recommendations = recommendations
        existing.record_count = len(records)
        existing.generated_at = datetime.utcnow()
        existing.model_used = MODEL
        db.commit()
        db.refresh(existing)
        return existing

    obj = SeniorAiSummary(
        senior_id=senior_id,
        trend_summary=trend_summary,
        anomaly_flags=anomaly_flags,
        recommendations=recommendations,
        record_count=len(records),
        model_used=MODEL,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# Plan SC: FR-06 — 캐시된 어르신 종합 요약 조회
def get_senior_summary(senior_id: int, db: Session) -> SeniorAiSummary:
    summary = db.query(SeniorAiSummary).filter(SeniorAiSummary.senior_id == senior_id).first()
    if not summary:
        raise HTTPException(
            status_code=404,
            detail="아직 생성된 요약이 없습니다. POST /ai/senior-summary/{senior_id} 를 먼저 호출하세요.",
        )
    return summary
