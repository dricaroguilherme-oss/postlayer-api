from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterPayload(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str | None = None


class LoginPayload(BaseModel):
    email: str
    password: str


class AuthUser(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    created_at: str
    updated_at: str


class AuthResponse(BaseModel):
    access_token: str
    user: AuthUser
