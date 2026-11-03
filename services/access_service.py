from sqlalchemy.orm import Session
from models import VisitSchedule

# ─────────────────────────────────────────────────────────
# 요양사 ↔ 어르신 "담당" 관계 정의 (B안: 일정 기반)
# C안 전환 시 이 파일의 두 함수 본문만 CaregiverSeniorAssignment 조회로 교체
# ─────────────────────────────────────────────────────────

def caregiver_senior_ids_subquery(caregiver_id: int, db: Session):
    """목록 필터용: 이 요양사가 담당하는 어르신 id 서브쿼리"""
    return (
        db.query(VisitSchedule.senior_id)                       # ① id 한 컬럼만
        .filter(VisitSchedule.caregiver_id == caregiver_id)     # ② 이 요양사의 일정만
        .distinct()                                             # ③ 중복 제거
    )


def is_caregiver_assigned(caregiver_id: int, senior_id: int, db: Session) -> bool:
    """단건 검사용: 이 요양사가 이 어르신을 담당하는가"""
    schedule = (
        db.query(VisitSchedule.id)  # 존재 여부만 보면 되니 가벼운 컬럼
        .filter(
            VisitSchedule.caregiver_id == caregiver_id,  # ② 두 조건 (쉼표 = AND)
            VisitSchedule.senior_id == senior_id,
        )
        .first()  # ① 실제 실행 → 행 or None
    )
    return schedule is not None                            # ③ 항상 True/False
