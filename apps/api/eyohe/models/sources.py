from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eyohe.core.db import Base, JSONType, TimestampMixin, UTCDateTime, UUIDMixin


class Source(UUIDMixin, TimestampMixin, Base):
    """A public location information was collected from (URL, API record, archive snapshot)."""

    __tablename__ = "sources"
    display_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(256), default="", nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    publisher: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    author: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    collector: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=5)  # 1 best … 5 unverified
    reliability_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="COLLECTED", nullable=False)
    language: Mapped[str | None] = mapped_column(String(16))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, default=dict, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    snapshots: Mapped[list[SourceSnapshot]] = relationship(
        back_populates="source", cascade="all, delete-orphan", order_by="SourceSnapshot.retrieved_at"
    )


class SourceSnapshot(UUIDMixin, Base):
    __tablename__ = "source_snapshots"
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    http_status: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    text_content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    artifact_path: Mapped[str | None] = mapped_column(Text)  # raw HTML/JSON file in the vault
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, default=dict, nullable=False)
    final_url: Mapped[str | None] = mapped_column(Text)
    fetch_ms: Mapped[int | None] = mapped_column(Integer)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    source: Mapped[Source] = relationship(back_populates="snapshots")


Index("ix_sources_case_canonical", Source.case_id, Source.canonical_url, unique=True)
