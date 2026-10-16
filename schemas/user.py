from pydantic import BaseModel
from typing import Optional
from models import UserRole


class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole
    full_name: Optional[str] = None
    phone: Optional[str] = None
    senior_ids: Optional[list[int]] = None  # Design Ref: §3 — guardian role 시 서버 검증 필수


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    role: UserRole
    refresh_token: str


class TokenData(BaseModel):
    username: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str


class LogoutRequest(BaseModel):
    refresh_token: str
