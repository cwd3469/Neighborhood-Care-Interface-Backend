from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# pool_pre_ping: 쓰기 전에 연결이 살아있는지 확인 — Neon처럼 유휴 시 잠드는 DB에서 끊긴 연결 오류 방지
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# DB 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
