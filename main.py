from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from models import Base
from routers import items, users, fhir ,questionnaire

Base.metadata.create_all(bind=engine)

app = FastAPI()


# CORS 미들웨어 — Next.js(3000) → FastAPI(8000) 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000" , "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(users.router)
app.include_router(items.router)
app.include_router(fhir.router)
app.include_router(questionnaire.router)