from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from eyohe.schemas.common import ORMModel


class TargetCreate(BaseModel):
    value: str = Field(min_length=1, max_length=1024)
    label: str = Field(default="", max_length=256)
    type: str | None = Field(default=None, description="Override auto-classification")
    is_primary: bool = False
    notes: str = ""


class TargetOut(ORMModel):
    id: UUID
    case_id: UUID
    type: str
    value: str
    normalized_value: str
    label: str
    notes: str
    is_primary: bool
    entity_id: UUID | None
    extra: dict[str, Any]
    created_at: datetime


class CaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = ""
    objective: str = ""
    priority: str = Field(default="MEDIUM", pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL)$")
    tags: list[str] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    classification: str = Field(default="RESEARCH", pattern=r"^(INTERNAL|RESEARCH|CONFIDENTIAL)$")


class CaseUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=256)
    description: str | None = None
    objective: str | None = None
    status: str | None = Field(default=None, pattern=r"^(DRAFT|ACTIVE|PAUSED|COMPLETED|ARCHIVED)$")
    priority: str | None = Field(default=None, pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL)$")
    tags: list[str] | None = None
    classification: str | None = Field(default=None, pattern=r"^(INTERNAL|RESEARCH|CONFIDENTIAL)$")


class CaseOut(ORMModel):
    id: UUID
    display_id: str
    name: str
    description: str
    objective: str
    status: str
    priority: str
    tags: list[Any]
    analyst_id: UUID | None
    is_demo: bool
    classification: str
    cloned_from_id: UUID | None
    closed_at: datetime | None
    evidence_count: int
    source_count: int
    entity_count: int
    finding_count: int
    created_at: datetime
    updated_at: datetime


class CaseDetail(CaseOut):
    targets: list[TargetOut] = Field(default_factory=list)


class NoteCreate(BaseModel):
    title: str = Field(default="", max_length=256)
    body: str = Field(min_length=1)
    pinned: bool = False


class NoteOut(ORMModel):
    id: UUID
    case_id: UUID
    author_id: UUID | None
    title: str
    body: str
    pinned: bool
    entity_refs: list[Any]
    evidence_refs: list[Any]
    created_at: datetime
    updated_at: datetime


class CloneRequest(BaseModel):
    name: str | None = Field(default=None, max_length=256)
