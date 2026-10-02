from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eyohe.core.db import Base, JSONType, TimestampMixin, UTCDateTime, UUIDMixin


class Finding(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "findings"
    display_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("investigations.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    assessment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="general", nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="UNVERIFIED", index=True)
    confidence_rationale: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    proposed_by: Mapped[str] = mapped_column(String(32), default="system", nullable=False)  # system|ai|analyst
    review_state: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    review_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    entity_ids: Mapped[list[Any]] = mapped_column(JSONType, default=list, nullable=False)
    relationship_ids: Mapped[list[Any]] = mapped_column(JSONType, default=list, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="INFO", nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    evidence_links: Mapped[list[FindingEvidence]] = relationship(back_populates="finding", cascade="all, delete-orphan")


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), primary_key=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="supports", nullable=False)  # supports|contradicts
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    finding: Mapped[Finding] = relationship(back_populates="evidence_links")


class TimelineEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "timeline_events"
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    precision: Mapped[str] = mapped_column(String(8), default="day", nullable=False)  # year|month|day|time
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    event_kind: Mapped[str] = mapped_column(String(32), default="OBSERVATION", nullable=False)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evidence.id", ondelete="SET NULL"))
    entity_ids: Mapped[list[Any]] = mapped_column(JSONType, default=list, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), default="UNVERIFIED", nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
