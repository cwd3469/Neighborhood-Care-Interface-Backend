from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import VisitRecord, VitalObservation
from schemas.record import VisitRecordCreate

# linkId → LOINC 코드 매핑 (FHIR QuestionnaireResponse item.linkId 기준)
VITAL_LINK_MAPPING: dict[str, dict] = {
    "blood-pressure-systolic":  {"loinc": "8480-6",   "display": "혈압(수축기)",  "unit": "mmHg"},
    "blood-pressure-diastolic": {"loinc": "8462-4",   "display": "혈압(이완기)",  "unit": "mmHg"},
    "heart-rate":               {"loinc": "8867-4",   "display": "맥박",          "unit": "beats/min"},
    "body-temperature":         {"loinc": "8310-5",   "display": "체온",          "unit": "Cel"},
    "blood-glucose":            {"loinc": "2339-0",   "display": "혈당",          "unit": "mg/dL"},
    "body-weight":              {"loinc": "29463-7",  "display": "체중",          "unit": "kg"},
    "oxygen-saturation":        {"loinc": "59408-5",  "display": "SpO₂",         "unit": "%"},
}


def _extract_value(answer: list[dict]) -> float | None:
    if not answer:
        return None
    a = answer[0]
    return a.get("valueDecimal") or a.get("valueInteger") or a.get("valueQuantity", {}).get("value")


def _build_fhir_observation(
    loinc_code: str,
    display: str,
    value: float,
    unit: str,
    senior_id: int,
    observed_at: datetime,
) -> dict:
    return {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": loinc_code, "display": display}]
        },
        "subject": {"reference": f"Patient/{senior_id}"},
        "effectiveDateTime": observed_at.isoformat(),
        "valueQuantity": {
            "value": value,
            "unit": unit,
            "system": "http://unitsofmeasure.org",
        },
    }


def _extract_vitals(
    fhir_response: dict,
    record_id: int,
    senior_id: int,
    observed_at: datetime,
) -> list[VitalObservation]:
    vitals: list[VitalObservation] = []
    items = fhir_response.get("item", [])

    for item in items:
        link_id = item.get("linkId", "")
        mapping = VITAL_LINK_MAPPING.get(link_id)
        if not mapping:
            continue

        value = _extract_value(item.get("answer", []))
        if value is None:
            continue

        fhir_obs = _build_fhir_observation(
            mapping["loinc"], mapping["display"], value, mapping["unit"],
            senior_id, observed_at,
        )
        vitals.append(VitalObservation(
            record_id=record_id,
            senior_id=senior_id,
            loinc_code=mapping["loinc"],
            display_name=mapping["display"],
            value=value,
            unit=mapping["unit"],
            observed_at=observed_at,
            fhir_observation=fhir_obs,
        ))
    return vitals


def create_record(data: VisitRecordCreate, caregiver_id: int, db: Session) -> VisitRecord:
    # authored 필드에서 관찰 시각 추출, 없으면 현재 시각
    authored_str = data.fhir_response.get("authored")
    try:
        observed_at = datetime.fromisoformat(authored_str) if authored_str else datetime.utcnow()
    except (ValueError, TypeError):
        observed_at = datetime.utcnow()

    record = VisitRecord(
        senior_id=data.senior_id,
        schedule_id=data.schedule_id,
        caregiver_id=caregiver_id,
        fhir_response=data.fhir_response,
        visit_notes=data.visit_notes,
        recorded_at=observed_at,
    )
    db.add(record)
    db.flush()  # record.id 확보

    vitals = _extract_vitals(data.fhir_response, record.id, data.senior_id, observed_at)
    for v in vitals:
        db.add(v)

    db.commit()
    db.refresh(record)
    return record


def get_records(
    db: Session,
    senior_id: int | None = None,
    caregiver_id: int | None = None,
) -> list[VisitRecord]:
    query = db.query(VisitRecord)
    if senior_id is not None:
        query = query.filter(VisitRecord.senior_id == senior_id)
    if caregiver_id is not None:
        query = query.filter(VisitRecord.caregiver_id == caregiver_id)
    return query.order_by(VisitRecord.recorded_at.desc()).all()


def get_record(record_id: int, db: Session) -> VisitRecord:
    record = db.query(VisitRecord).filter(VisitRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="방문 기록을 찾을 수 없습니다")
    return record
