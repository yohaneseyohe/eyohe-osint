from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eyohe.core.db import Base, JSONType, TimestampMixin, UTCDateTime, UUIDMixin
from eyohe.models.cases import Case


class Investigation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "investigations"
    display_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    request_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    objective: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT", index=True)
    plan: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    plan_rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    plan_source: Mapped[str] = mapped_column(String(32), default="template", nullable=False)  # template|ollama
    bounds: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    control_flag: Mapped[str | None] = mapped_column(String(16))  # pause|stop requested
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    event_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    case: Mapped[Case] = relationship(back_populates="investigations")
    tasks: Mapped[list[InvestigationTask]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan", order_by="InvestigationTask.order"
    )


class InvestigationTask(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "investigation_tasks"
    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)  # maps to a tool/collector
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    result_summary: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    category: Mapped[str] = mapped_column(String(32), default="search", nullable=False)  # for completeness %

    investigation: Mapped[Investigation] = relationship(back_populates="tasks")


class InvestigationEvent(UUIDMixin, Base):
    """Append-only live feed. ``seq`` is monotonic per investigation for SSE replay."""

    __tablename__ = "investigation_events"
    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="SYSTEM")  # PLAN/SEARCH/DNS/...
    message: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(String(8), nullable=False, default="info")
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("investigation_tasks.id", ondelete="SET NULL"))
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)


class SearchQuery(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "search_queries"
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("investigation_tasks.id", ondelete="SET NULL"))
    branch: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class SearchResult(UUIDMixin, Base):
    __tablename__ = "search_results"
    query_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_queries.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(256), default="", nullable=False, index=True)
    snippet: Mapped[str] = mapped_column(Text, default="", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    engine: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    relevance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="NEW", nullable=False)  # NEW/SAVED/IGNORED
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False)


Index("ix_investigation_events_inv_seq", InvestigationEvent.investigation_id, InvestigationEvent.seq, unique=True)
Index("ix_search_results_case_canonical", SearchResult.case_id, SearchResult.canonical_url)
