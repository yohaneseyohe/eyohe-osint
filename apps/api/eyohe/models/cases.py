from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eyohe.core.db import Base, JSONType, TimestampMixin, UTCDateTime, UUIDMixin

if TYPE_CHECKING:
    from eyohe.models.investigations import Investigation


class Case(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "cases"
    display_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    objective: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT", index=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")
    tags: Mapped[list[Any]] = mapped_column(JSONType, default=list, nullable=False)
    analyst_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    classification: Mapped[str] = mapped_column(String(16), default="RESEARCH", nullable=False)
    cloned_from_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"))
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Denormalized counters refreshed by services (cheap dashboard rendering).
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    entity_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    targets: Mapped[list[Target]] = relationship(back_populates="case", cascade="all, delete-orphan")
    investigations: Mapped[list[Investigation]] = relationship(back_populates="case", cascade="all, delete-orphan")
    notes: Mapped[list[Note]] = relationship(back_populates="case", cascade="all, delete-orphan")


class Target(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "targets"
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(1024), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"))
    extra: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    case: Mapped[Case] = relationship(back_populates="targets")


class Note(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notes"
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)  # Markdown; may reference EYO-EV-… ids
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    entity_refs: Mapped[list[Any]] = mapped_column(JSONType, default=list, nullable=False)
    evidence_refs: Mapped[list[Any]] = mapped_column(JSONType, default=list, nullable=False)
    attachments: Mapped[list[Any]] = mapped_column(JSONType, default=list, nullable=False)

    case: Mapped[Case] = relationship(back_populates="notes")


Index("ix_targets_case_type_value", Target.case_id, Target.type, Target.normalized_value, unique=True)
