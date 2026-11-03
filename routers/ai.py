from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from schemas.ai_summary import AiSummaryResponse, SeniorAiSummaryResponse
from services.ai_service import generate_summary, get_summary, generate_senior_summary, get_senior_summary
from routers.users import get_current_user, check_senior_access
from models import User, VisitRecord

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/summarize/{record_id}", response_model=AiSummaryResponse)
def summarize(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """방문 기록 텍스트 + 활력징후를 LLM으로 요약하고 이상징후를 하이라이트합니다."""
    # Plan SC: FR-07 — guardian 소유 검사
    record = db.query(VisitRecord).filter(VisitRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="방문 기록을 찾을 수 없습니다")
    check_senior_access(record.senior_id, current_user, db)
    return generate_summary(record_id, db)


@router.get("/summary/{record_id}", response_model=AiSummaryResponse)
def get_cached_summary(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """캐시된 AI 요약 조회 (없으면 404, POST /ai/summarize 먼저 호출)."""
    # Plan SC: FR-07 — guardian 소유 검사
    record = db.query(VisitRecord).filter(VisitRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="방문 기록을 찾을 수 없습니다")
    check_senior_access(record.senior_id, current_user, db)
    return get_summary(record_id, db)


@router.post("/senior-summary/{senior_id}", response_model=SeniorAiSummaryResponse)
def summarize_senior(
    senior_id: int,
    limit: int = Query(default=10, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """어르신의 최근 N건 방문 기록을 누적 분석하여 종합 요약을 생성합니다."""
    # Plan SC: FR-07 — guardian 소유 검사
    check_senior_access(senior_id, current_user, db)
    return generate_senior_summary(senior_id, limit, db)


@router.get("/senior-summary/{senior_id}", response_model=SeniorAiSummaryResponse)
def get_cached_senior_summary(
    senior_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """캐시된 어르신 종합 요약 조회 (없으면 404, POST /ai/senior-summary 먼저 호출)."""
    # Plan SC: FR-07 — guardian 소유 검사
    check_senior_access(senior_id, current_user, db)
    return get_senior_summary(senior_id, db)
