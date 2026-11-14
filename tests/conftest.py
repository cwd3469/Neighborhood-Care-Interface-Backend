"""
테스트 공통 설정 — 운영 DB(Neon)와 분리된 SQLite 인메모리 DB를 쓴다.

순서가 중요하다:
1) 앱 모듈을 import 하기 전에 환경변수를 먼저 넣는다
   (config.py가 import 시점에 DATABASE_URL / SECRET_KEY를 읽고,
    ai_service.py가 import 시점에 Anthropic 클라이언트를 만들기 때문)
2) get_db 의존성을 테스트 세션으로 바꿔 끼운다 (dependency_overrides)
"""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ.setdefault("ANTHROPIC_API_KEY", "test-dummy-key")  # 실제 호출은 하지 않음

from datetime import date, datetime, time  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from auth import create_access_token, hash_password  # noqa: E402
from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    GuardianSeniorRelation, Senior, User, UserRole, VisitRecord, VisitSchedule,
)

# 인메모리 SQLite는 연결마다 DB가 따로 생기므로 StaticPool로 연결 1개를 공유한다
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# bcrypt는 느리므로 해시는 한 번만 만든다
_PASSWORD = "pass1234"
_HASHED = hash_password(_PASSWORD)


def _override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture()
def db():
    """테스트마다 테이블을 새로 만들고 끝나면 지운다 — 테스트끼리 데이터가 섞이지 않게"""
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    return TestClient(app)


@pytest.fixture()
def seed(db):
    """
    권한 테스트용 고정 데이터

    어르신      S1, S2
    요양사      cg_a (S1 담당), cg_b (S1·S2 담당)
    보호자      g1 → S1, g2 → S2
    일정        sch_a1: S1·cg_a / sch_b2: S2·cg_b / sch_b1: S1·cg_b
    기록        rec_a1: S1·cg_a / rec_b2: S2·cg_b / rec_b1: S1·cg_b
    """
    def user(username, role):
        u = User(username=username, hashed_password=_HASHED, role=role, full_name=username)
        db.add(u)
        return u

    admin = user("admin", UserRole.admin)
    cg_a = user("cg_a", UserRole.caregiver)
    cg_b = user("cg_b", UserRole.caregiver)
    g1 = user("g1", UserRole.guardian)
    g2 = user("g2", UserRole.guardian)

    s1 = Senior(full_name="어르신1", birth_date=date(1940, 1, 1), gender="F")
    s2 = Senior(full_name="어르신2", birth_date=date(1942, 2, 2), gender="M")
    db.add_all([s1, s2])
    db.flush()

    db.add_all([
        GuardianSeniorRelation(guardian_id=g1.id, senior_id=s1.id, relation="자녀"),
        GuardianSeniorRelation(guardian_id=g2.id, senior_id=s2.id, relation="자녀"),
    ])

    def schedule(senior, caregiver):
        s = VisitSchedule(
            senior_id=senior.id, caregiver_id=caregiver.id,
            scheduled_date=date(2026, 11, 20), start_time=time(10), end_time=time(11),
            created_by=admin.id,
        )
        db.add(s)
        return s

    sch_a1 = schedule(s1, cg_a)
    sch_b2 = schedule(s2, cg_b)
    sch_b1 = schedule(s1, cg_b)
    db.flush()

    def record(senior, caregiver, sch):
        r = VisitRecord(
            senior_id=senior.id, caregiver_id=caregiver.id, schedule_id=sch.id,
            fhir_response={"resourceType": "QuestionnaireResponse", "item": []},
            recorded_at=datetime(2026, 11, 20, 10, 30),
        )
        db.add(r)
        return r

    rec_a1 = record(s1, cg_a, sch_a1)
    rec_b2 = record(s2, cg_b, sch_b2)
    rec_b1 = record(s1, cg_b, sch_b1)
    db.commit()

    users = {u.username: u for u in (admin, cg_a, cg_b, g1, g2)}
    return {
        "users": users,
        "headers": {
            name: {"Authorization": f"Bearer {create_access_token({'sub': name})}"}
            for name in users
        },
        "s1": s1.id, "s2": s2.id,
        "sch_a1": sch_a1.id, "sch_b2": sch_b2.id, "sch_b1": sch_b1.id,
        "rec_a1": rec_a1.id, "rec_b2": rec_b2.id, "rec_b1": rec_b1.id,
    }
