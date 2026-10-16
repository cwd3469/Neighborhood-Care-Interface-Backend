from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from models import Base
from routers import users, seniors, schedules, records, vitals, ai, auth

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="우리 동네 시니어 케어 매니저",
    description="방문요양·건강기록 관리 SaaS — FHIR R5 기반",
    version="1.0.0",
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(seniors.router)
app.include_router(schedules.router)
app.include_router(records.router)
app.include_router(vitals.router)
app.include_router(ai.router)
