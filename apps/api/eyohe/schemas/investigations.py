from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from eyohe.schemas.common import ORMModel


class InvestigationStart(BaseModel):
    case_id: UUID
    request_text: str = Field(default="", max_length=4000, description="Natural-language investigation request")
    target_id: UUID | None = None
    name: str | None = Field(default=None, max_length=256)
    bounds: dict[str, int] | None = None
    use_ai: bool = True
    auto_approve: bool = False


class TaskOut(ORMModel):
    id: UUID
    order: int
    task_type: str
    title: str
    rationale: str
    status: str
    enabled: bool
    category: str
    params: dict[str, Any]
    result_summary: dict[str, Any]
    error: str | None
    attempts: int
    started_at: datetime | None
    finished_at: datetime | None


class InvestigationOut(ORMModel):
    id: UUID
    display_id: str
    case_id: UUID
    name: str
    request_text: str
    objective: str
    status: str
    plan: dict[str, Any]
    plan_rationale: str
    plan_source: str
    bounds: dict[str, Any]
    stats: dict[str, Any]
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    approved_at: datetime | None
    event_seq: int
    created_at: datetime
    updated_at: datetime


class InvestigationDetail(InvestigationOut):
    tasks: list[TaskOut] = Field(default_factory=list)


class TaskChange(BaseModel):
    id: UUID
    enabled: bool | None = None
    params: dict[str, Any] | None = None


class PlanUpdate(BaseModel):
    tasks: list[TaskChange] = Field(default_factory=list)


class CustomTask(BaseModel):
    task_type: str
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class ControlRequest(BaseModel):
    action: str = Field(pattern=r"^(pause|resume|stop)$")


class EventOut(BaseModel):
    id: str
    investigation_id: str
    case_id: str
    seq: int
    created_at: str
    event_type: str
    stage: str
    message: str
    level: str
    task_id: str | None
    data: dict[str, Any]
