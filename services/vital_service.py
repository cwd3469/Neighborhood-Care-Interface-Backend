from sqlalchemy.orm import Session
from models import VitalObservation


def get_vitals_for_record(record_id: int, db: Session) -> list[VitalObservation]:
    return (
        db.query(VitalObservation)
        .filter(VitalObservation.record_id == record_id)
        .order_by(VitalObservation.loinc_code)
        .all()
    )


def get_vitals_for_senior(
    senior_id: int,
    db: Session,
    loinc_code: str | None = None,
    limit: int = 100,
) -> list[VitalObservation]:
    query = db.query(VitalObservation).filter(VitalObservation.senior_id == senior_id)
    if loinc_code:
        query = query.filter(VitalObservation.loinc_code == loinc_code)
    return query.order_by(VitalObservation.observed_at.desc()).limit(limit).all()
