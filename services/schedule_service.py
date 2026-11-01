from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import VisitSchedule, ScheduleStatus, GuardianSeniorRelation
from schemas.schedule import ScheduleCreate, ScheduleUpdate


def create_schedule(data: ScheduleCreate, created_by: int, db: Session) -> VisitSchedule:
    schedule = VisitSchedule(**data.model_dump(), created_by=created_by)
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def get_schedules(
    db: Session,
    caregiver_id: int | None = None,
    senior_id: int | None = None,
) -> list[VisitSchedule]:
    query = db.query(VisitSchedule)
    if caregiver_id is not None:
        query = query.filter(VisitSchedule.caregiver_id == caregiver_id)
    if senior_id is not None:
        query = query.filter(VisitSchedule.senior_id == senior_id)
    return query.order_by(VisitSchedule.scheduled_date, VisitSchedule.start_time).all()


def get_schedule(schedule_id: int, db: Session) -> VisitSchedule:
    schedule = db.query(VisitSchedule).filter(VisitSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다")
    return schedule


def update_schedule(schedule_id: int, data: ScheduleUpdate, db: Session) -> VisitSchedule:
    schedule = get_schedule(schedule_id, db)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(schedule, field, value)
    db.commit()
    db.refresh(schedule)
    return schedule


def update_schedule_status(schedule_id: int, status: ScheduleStatus, db: Session) -> VisitSchedule:
    schedule = get_schedule(schedule_id, db)
    schedule.status = status
    db.commit()
    db.refresh(schedule)
    return schedule


def delete_schedule(schedule_id: int, db: Session) -> dict:
    schedule = get_schedule(schedule_id, db)
    db.delete(schedule)
    db.commit()
    return {"detail": "삭제되었습니다"}

# 보호자랑 매칭된 어르신에 스케줄 확인 기능
def get_schedules_for_guardian(guardian_id: int, db: Session, senior_id: int | None = None) -> list[
    type[VisitSchedule]]:
    # 1) 이 보호자가 맡은 어르신 id 목록 (서브쿼리 — 아직 실행 안 됨)
    allowed_senior_ids = db.query(GuardianSeniorRelation.senior_id).filter(
        GuardianSeniorRelation.guardian_id == guardian_id
    )
    # 2) 일정 테이블에서, 그 목록 안의 어르신 일정만
    query = db.query(VisitSchedule).filter(
        VisitSchedule.senior_id.in_(allowed_senior_ids)
    )
    # 3) 특정 어르신만 보고 싶을 때 (남의 어르신 id면 1)에 걸려서 자동으로 [])
    if senior_id is not None:
        query = query.filter(VisitSchedule.senior_id == senior_id)

    return query.order_by(VisitSchedule.scheduled_date, VisitSchedule.start_time).all()

