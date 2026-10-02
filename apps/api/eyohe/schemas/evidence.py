from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from eyohe.schemas.common import ORMModel


class SourceOut(ORMModel):
    id: UUID
    display_id: str
    case_id: UUID
    source_type: str
    url: str
    canonical_url: str
    domain: str
    title: str
    publisher: str
    author: str
    published_at: datetime | None
    collected_at: datetime
    collector: str
    tier: int
    reliability_note: str
    status: str
    is_demo: bool
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")


class SnapshotOut(ORMModel):
    id: UUID
    source_id: UUID
    retrieved_at: datetime
    http_status: int | None
    content_type: str
    title: str
    content_hash: str
    text_chars: int
    artifact_path: str | None
    final_url: str | None
    fetch_ms: int | None
    truncated: bool
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")


class SnapshotDetail(SnapshotOut):
    text_content: str


class SourceDetail(SourceOut):
    snapshots: list[SnapshotOut] = Field(default_factory=list)
    evidence_count: int = 0


class ArtifactOut(ORMModel):
    id: UUID
    kind: str
    path: str
    mime_type: str
    sha256: str
    size_bytes: int
    original_url: str | None
    created_at: datetime


class EvidenceOut(ORMModel):
    id: UUID
    display_id: str
    case_id: UUID
    investigation_id: UUID | None
    source_id: UUID | None
    snapshot_id: UUID | None
    evidence_type: str
    claim: str
    excerpt: str
    excerpt_verified: bool
    context: str
    collector: str
    collection_method: str
    collected_at: datetime
    observed_at: datetime | None
    confidence: str
    review_state: str
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_note: str
    content_hash: str
    structured: dict[str, Any]
    entity_ids: list[Any]
    is_demo: bool
    redacted: bool
    created_at: datetime


class EvidenceDetail(EvidenceOut):
    source: SourceOut | None = None
    artifacts: list[ArtifactOut] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceCreate(BaseModel):
    claim: str = Field(min_length=1, max_length=4000)
    evidence_type: str = "DIRECT_STATEMENT"
    source_id: UUID | None = None
    source_url: str | None = None
    excerpt: str = ""
    context: str = ""
    observed_at: datetime | None = None
    entity_ids: list[UUID] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    state: str = Field(pattern=r"^(ACCEPTED|REJECTED|NEEDS_VERIFICATION|PENDING)$")
    note: str = Field(default="", max_length=4000)
