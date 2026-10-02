from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from eyohe.schemas.common import ORMModel


class FindingOut(ORMModel):
    id: UUID
    display_id: str
    case_id: UUID
    investigation_id: UUID | None
    title: str
    claim: str
    assessment: str
    category: str
    confidence: str
    confidence_rationale: dict[str, Any]
    proposed_by: str
    review_state: str
    review_note: str
    entity_ids: list[Any]
    relationship_ids: list[Any]
    severity: str
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class FindingDetail(FindingOut):
    supporting: list[dict[str, Any]] = Field(default_factory=list)
    contradicting: list[dict[str, Any]] = Field(default_factory=list)


class FindingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    claim: str = Field(min_length=1)
    assessment: str = ""
    category: str = "general"
    supporting: list[UUID] = Field(default_factory=list)
    contradicting: list[UUID] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    severity: str = "INFO"


class AttachEvidence(BaseModel):
    evidence_id: UUID
    role: str = Field(default="supports", pattern=r"^(supports|contradicts)$")


class TimelineOut(ORMModel):
    id: UUID
    case_id: UUID
    occurred_at: datetime
    precision: str
    title: str
    description: str
    event_kind: str
    evidence_id: UUID | None
    entity_ids: list[Any]
    confidence: str
    is_demo: bool


class WhyOut(BaseModel):
    finding: FindingOut
    confidence: dict[str, Any]
    chain: list[dict[str, Any]]
    reasoning: str
