from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 50


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class OkResponse(BaseModel):
    ok: bool = True
    message: str = ""


class IdResponse(BaseModel):
    id: UUID
    display_id: str | None = None


class Timestamped(ORMModel):
    created_at: datetime
    updated_at: datetime
