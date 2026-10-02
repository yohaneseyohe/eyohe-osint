from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eyohe.core.db import Base, JSONType, TimestampMixin, UTCDateTime, UUIDMixin


class Entity(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "entities"
    display_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="UNVERIFIED")
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence_ids: Mapped[list[Any]] = mapped_column(JSONType, default=list, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    is_target: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"))

    aliases: Mapped[list[EntityAlias]] = relationship(back_populates="entity", cascade="all, delete-orphan")


class EntityAlias(UUIDMixin, Base):
    __tablename__ = "entity_aliases"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    alias_type: Mapped[str] = mapped_column(String(32), default="name", nullable=False)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evidence.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    entity: Mapped[Entity] = relationship(back_populates="aliases")


class Relationship(UUIDMixin, TimestampMixin, Base):
    """Every relationship must be backed by at least one evidence row via relationship_evidence."""

    __tablename__ = "relationships"
    display_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="UNVERIFIED")
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    review_state: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    review_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    evidence_links: Mapped[list[RelationshipEvidence]] = relationship(
        back_populates="relationship_", cascade="all, delete-orphan"
    )


class RelationshipEvidence(Base):
    __tablename__ = "relationship_evidence"
    relationship_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationships.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="supports", nullable=False)  # supports|contradicts

    relationship_: Mapped[Relationship] = relationship(back_populates="evidence_links")


Index("ix_entities_case_type_value", Entity.case_id, Entity.type, Entity.normalized_value, unique=True)
Index(
    "ix_relationships_unique",
    Relationship.case_id,
    Relationship.source_entity_id,
    Relationship.target_entity_id,
    Relationship.type,
    unique=True,
)
