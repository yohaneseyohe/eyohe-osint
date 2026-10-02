from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from eyohe.schemas.common import ORMModel


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=512)


class SetupRequest(BaseModel):
    email: str = Field(max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    username: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(min_length=10, max_length=512)
    display_name: str = Field(default="", max_length=128)


class CreateUserRequest(SetupRequest):
    role: str = Field(default="analyst", pattern=r"^(admin|analyst|viewer)$")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=512)


class UserOut(ORMModel):
    id: UUID
    email: str
    username: str
    display_name: str
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str
    expires_at: datetime


class SetupStatus(BaseModel):
    needs_setup: bool
    user_count: int


class ApiTokenOut(ORMModel):
    id: UUID
    name: str
    created_at: datetime
    last_used_at: datetime | None
    revoked: bool


class ApiTokenCreated(ApiTokenOut):
    token: str
