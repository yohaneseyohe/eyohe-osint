from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eyohe.core.db import Base, JSONType, TimestampMixin, UTCDateTime, UUIDMixin


class Report(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reports"
    display_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    classification: Mapped[str] = mapped_column(String(16), default="RESEARCH", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    generation_ms: Mapped[int | None] = mapped_column(Integer)
    options: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

    sections: Mapped[list[ReportSection]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="ReportSection.order"
    )


class ReportSection(UUIDMixin, Base):
    __tablename__ = "report_sections"
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    cited_ids: Mapped[list[Any]] = mapped_column(JSONType, default=list, nullable=False)

    report: Mapped[Report] = relationship(back_populates="sections")
