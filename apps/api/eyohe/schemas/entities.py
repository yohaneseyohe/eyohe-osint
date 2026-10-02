from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from eyohe.schemas.common import ORMModel


class EntityOut(ORMModel):
    id: UUID
    display_id: str
    case_id: UUID
    type: str
    value: str
    normalized_value: str
    label: str
    first_seen: datetime
    last_seen: datetime
    confidence: str
    source_count: int
    evidence_ids: list[Any]
    attributes: dict[str, Any]
    is_target: bool
    is_demo: bool
    created_at: datetime


class EntityCreate(BaseModel):
    type: str
    value: str = Field(min_length=1, max_length=2000)
    label: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    evidence_id: UUID | None = None


class RelationshipOut(ORMModel):
    id: UUID
    display_id: str
    case_id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    type: str
    confidence: str
    rationale: str
    review_state: str
    review_note: str
    attributes: dict[str, Any]
    is_demo: bool
    created_at: datetime


class RelationshipDetail(RelationshipOut):
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    source_entity: EntityOut | None = None
    target_entity: EntityOut | None = None
    why: dict[str, Any] = Field(default_factory=dict)


class RelationshipCreate(BaseModel):
    source_entity_id: UUID
    target_entity_id: UUID
    type: str
    evidence_ids: list[UUID] = Field(min_length=1)
    rationale: str = ""


class GraphNode(BaseModel):
    id: str
    display_id: str
    type: str
    label: str
    value: str
    confidence: str
    is_target: bool
    evidence_count: int
    attributes: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    display_id: str
    source: str
    target: str
    type: str
    confidence: str
    review_state: str
    evidence_count: int
    rationale: str


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stats: dict[str, Any] = Field(default_factory=dict)
