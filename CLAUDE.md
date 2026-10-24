# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI backend that accepts FHIR R5 Questionnaire JSON and uses the Claude API (claude-sonnet-4) to generate React TypeScript components and HTML previews. The core value: medical teams can auto-generate form UIs from FHIR Questionnaires without manual coding.

## Commands

```bash
# Local development
source venv/bin/activate
uvicorn main:app --reload        # runs on http://localhost:8000
# API docs available at http://localhost:8000/docs

# Docker (with PostgreSQL)
docker-compose up --build

# Install dependencies
pip install -r requirements.txt
```

## Environment Variables (.env)

```
ANTHROPIC_API_KEY=...
DATABASE_URL=sqlite:///./items.db   # local dev; PostgreSQL in Docker
SECRET_KEY=...
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Architecture

```
main.py              → FastAPI app entry, CORS config, router registration
config.py            → Loads .env; exports SECRET_KEY, DATABASE_URL, etc.
database.py          → SQLAlchemy engine + get_db() dependency
auth.py              → JWT create/decode, bcrypt password hashing
models.py            → SQLAlchemy ORM models (User, Item, Questionnaire)
routers/             → Route handlers (thin layer — delegates to services)
schemas/             → Pydantic v2 request/response models
services/            → Business logic
```

### Key Data Flow — FHIR Component Generation

1. `POST /fhir/generate` → `routers/fhir.py`
2. Pydantic validation in `schemas/fhir.py`:
   - `FhirQuestionnaireRequest.validate_fhir_questionnaire` calls `fhir.resources.Questionnaire.model_validate()` — invalid FHIR R5 → 422
   - `component_name` must be PascalCase
3. `FhirClaudeService.generate_component()` in `services/fhir_claude_service.py`:
   - Builds a Korean-language prompt with the FHIR JSON
   - Calls `client.messages.create()` (Anthropic SDK, model `claude-sonnet-4-20250514`)
   - Expects raw JSON response (no markdown fences) with keys: `component_code`, `preview_html`, `warnings`
4. Returns `FhirComponentResponse` with TSX code + full HTML document (Tailwind CDN)

### Authentication

All `/questionnaire` routes require JWT Bearer token. Auth flow:
- `POST /register` → bcrypt-hash password, save User
- `POST /login` → verify password, return JWT
- Protected routes use `get_current_user` dependency from `routers/users.py`

### Database

- **Local dev**: SQLite (`items.db`) — `DATABASE_URL=sqlite:///./items.db`
- **Docker/Production**: PostgreSQL 15 via `docker-compose.yml`
- Tables auto-created on startup: `Base.metadata.create_all(bind=engine)` in `main.py`
- `Questionnaire.questionnaire` column is typed `Float` (likely a bug — should be `Text` or `JSON` for storing FHIR JSON)

## FHIR Item Type → React Component Mapping

| FHIR type | React element |
|-----------|---------------|
| string    | `<input type="text" />` |
| boolean   | `<input type="checkbox" />` |
| integer   | `<input type="number" />` |
| choice    | `<select />` |
| date      | `<input type="date" />` |

## Adding a New Router

1. Create `routers/<name>.py` with `router = APIRouter(prefix="/<name>", tags=["<name>"])`
2. Create `schemas/<name>.py` for Pydantic models
3. Create `services/<name>_service.py` for business logic
4. Register in `main.py`: `app.include_router(<name>.router)`
