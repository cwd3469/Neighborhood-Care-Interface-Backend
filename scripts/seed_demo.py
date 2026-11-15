"""데모용 계정·데이터 생성 스크립트 (한 번만 실행)

만드는 것 (모두 더미 데이터):
- 요양사 demo_caregiver, 보호자 demo_guardian — 비밀번호는 실행할 때 입력 (저장소에 남기지 않음)
- 어르신 2명: 김순자(보호자 연결 O), 박영호(보호자 연결 X — 권한 데모용)
- 김순자 과거 방문 3건 + 기록 3건 (정상 / 혈압 상승 / 발열) — 활력징후 포함 FHIR QuestionnaireResponse
- 김순자 오늘 일정 1건 (상태: 예정 — 데모 중에 '방문 시작 → 완료 → 기록 작성'을 직접 시연)
- 박영호 오늘 일정 1건

기록은 record_service.create_record로 만든다 → API와 같은 경로로 vital_observations까지 생성.
AI 요약은 만들지 않는다 (데모 중 보호자 화면에서 처음 생성되는 모습을 보여주기 위해).

사용법 (backend 폴더에서, 관리자 계정이 먼저 있어야 함 — scripts/create_admin.py):
    DATABASE_URL='postgresql://...neon.tech/...?sslmode=require' python scripts/seed_demo.py
"""
import getpass
import os
import sys
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import hash_password  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from models import (  # noqa: E402
    GuardianSeniorRelation, ScheduleStatus, Senior, User, UserRole, VisitSchedule,
)
from schemas.record import VisitRecordCreate  # noqa: E402
from services.record_service import create_record  # noqa: E402

CAREGIVER = "demo_caregiver"
GUARDIAN = "demo_guardian"

# docs/visit-record-examples.md 1·2·4번 케이스
PAST_VISITS = [
    {
        "days_ago": 6,
        "notes": "09:00~12:00 방문. 아침 식사(죽 1공기, 반찬 3종) 전량 섭취. 아침 약(혈압약) 복용 확인. "
                 "세면·옷 갈아입기 보조, 거실 청소. 30분 동안 아파트 단지 산책, 보행 안정적. "
                 "기분 좋으시고 손녀 이야기 많이 하심. 특이사항 없음.",
        "vitals": {"blood-pressure-systolic": 128, "blood-pressure-diastolic": 78,
                   "heart-rate": 72, "body-temperature": 36.5, "oxygen-saturation": 97},
    },
    {
        "days_ago": 4,
        "notes": "10:00~13:00 방문. 도착 시 뒷목이 뻐근하고 머리가 무겁다고 하심. 어젯밤 잠을 거의 못 주무셨다고 함. "
                 "아침 혈압약은 복용하셨다고 하나 약통 확인 결과 어제 저녁분이 남아 있음. "
                 "10분 휴식 후 재측정했으나 비슷한 수치. 짠 음식(라면) 드셨다고 하심. 보호자께 연락 권장.",
        "vitals": {"blood-pressure-systolic": 162, "blood-pressure-diastolic": 98,
                   "heart-rate": 88, "body-temperature": 36.6},
    },
    {
        "days_ago": 2,
        "notes": "09:00~12:00 방문. 이틀 전부터 기침, 오늘은 누런 가래 있음. 몸이 으슬으슬하다고 하심. "
                 "식사 절반만 드심. 물 3컵 드시게 함. 숨이 조금 차다고 하심. 보호자께 병원 진료 권유 문자 드림.",
        "vitals": {"body-temperature": 38.2, "oxygen-saturation": 92, "heart-rate": 102,
                   "blood-pressure-systolic": 132, "blood-pressure-diastolic": 80},
    },
]


def _questionnaire_response(senior_id: int, authored: datetime, vitals: dict) -> dict:
    items = []
    for link_id, value in vitals.items():
        key = "valueInteger" if isinstance(value, int) else "valueDecimal"
        items.append({"linkId": link_id, "answer": [{key: value}]})
    return {
        "resourceType": "QuestionnaireResponse",
        "status": "completed",
        "subject": {"reference": f"Patient/{senior_id}"},
        "authored": authored.isoformat(),
        "item": items,
    }


def main() -> None:
    url = os.getenv("DATABASE_URL", "")
    host = url.split("@")[-1].split("/")[0] if "@" in url else url
    print(f"대상 DB: {host}")
    if input("이 DB에 데모 데이터를 만들까요? (y/N) ").strip().lower() != "y":
        print("취소했습니다.")
        return

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.admin).first()
        if admin is None:
            print("관리자 계정이 없습니다. scripts/create_admin.py를 먼저 실행하세요.")
            return
        if db.query(User).filter(User.username.in_([CAREGIVER, GUARDIAN])).first():
            print("데모 계정이 이미 있습니다. 변경하지 않았습니다.")
            return

        password = getpass.getpass("데모 계정 공통 비밀번호 (8자 이상, 화면에 안 보임): ")
        if len(password) < 8:
            print("비밀번호는 8자 이상이어야 합니다.")
            return
        hashed = hash_password(password)

        caregiver = User(username=CAREGIVER, hashed_password=hashed, role=UserRole.caregiver,
                         full_name="이미영", phone="010-0000-0001")
        guardian = User(username=GUARDIAN, hashed_password=hashed, role=UserRole.guardian,
                        full_name="김지훈", phone="010-0000-0002")
        s1 = Senior(full_name="김순자", birth_date=date(1941, 3, 12), gender="F",
                    address="서울시 마포구 (더미)", medical_notes="고혈압 (더미 데이터)")
        s2 = Senior(full_name="박영호", birth_date=date(1938, 8, 25), gender="M",
                    address="서울시 은평구 (더미)", medical_notes="당뇨 (더미 데이터)")
        db.add_all([caregiver, guardian, s1, s2])
        db.flush()
        db.add(GuardianSeniorRelation(guardian_id=guardian.id, senior_id=s1.id, relation="자녀"))

        today = date.today()

        def schedule(senior, day, status, start=time(9), end=time(12)):
            sch = VisitSchedule(senior_id=senior.id, caregiver_id=caregiver.id, scheduled_date=day,
                                start_time=start, end_time=end, status=status, created_by=admin.id)
            db.add(sch)
            db.flush()
            return sch

        past = []
        for visit in PAST_VISITS:
            day = today - timedelta(days=visit["days_ago"])
            past.append((schedule(s1, day, ScheduleStatus.completed), day, visit))
        schedule(s1, today, ScheduleStatus.scheduled, time(14), time(17))
        schedule(s2, today, ScheduleStatus.scheduled, time(10), time(12))
        db.commit()

        for sch, day, visit in past:
            authored = datetime.combine(day, time(11, 30))
            create_record(
                VisitRecordCreate(
                    senior_id=s1.id, schedule_id=sch.id, visit_notes=visit["notes"],
                    fhir_response=_questionnaire_response(s1.id, authored, visit["vitals"]),
                ),
                caregiver_id=caregiver.id, db=db,
            )

        print("완료:")
        print(f"  요양사 {CAREGIVER} / 보호자 {GUARDIAN} (비밀번호: 방금 입력한 값)")
        print(f"  어르신 김순자 id={s1.id} (보호자 연결), 박영호 id={s2.id} (보호자 연결 안 됨)")
        print(f"  과거 기록 {len(past)}건, 오늘 일정 2건")
    finally:
        db.close()


if __name__ == "__main__":
    main()
