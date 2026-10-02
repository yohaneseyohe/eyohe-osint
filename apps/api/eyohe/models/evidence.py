from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eyohe.core.db import Base, JSONType, TimestampMixin, UTCDateTime, UUIDMixin


class Evidence(UUIDMixin, TimestampMixin, Base):
    """Immutable-ish record: fields describing *what was observed* never change after creation;
    only review state and analyst annotations are mutable."""

    __tablename__ = "evidence"
    display_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("investigations.id", ondelete="SET NULL"), index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), index=True)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_snapshots.id", ondelete="SET NULL"))
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    excerpt_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    collector: Mapped[str] = mapped_column(String(64), nullable=False)
    collection_method: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # when the source says it happened
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="UNVERIFIED", index=True)
    review_state: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    review_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    structured: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    entity_ids: Mapped[list[Any]] = mapped_column(JSONType, default=list, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    redacted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    artifacts: Mapped[list[EvidenceArtifact]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan", lazy="selectin"
    )


class EvidenceArtifact(UUIDMixin, Base):
    __tablename__ = "evidence_artifacts"
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # html|json|screenshot|pdf|document|text
    path: Mapped[str] = mapped_column(Text, nullable=False)  # relative to DATA_DIR/evidence
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    original_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, default=dict, nullable=False)

    evidence: Mapped[Evidence] = relationship(back_populates="artifacts")
