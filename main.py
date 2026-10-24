import os
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

# 허용할 프론트 주소 — 쉼표로 구분 (예: "https://my-app.vercel.app,http://localhost:3000")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
