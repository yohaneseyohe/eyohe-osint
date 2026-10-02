from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from eyohe.core.db import Base, JSONType, TimestampMixin, UTCDateTime, UUIDMixin


class Monitor(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "monitors"
    display_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("targets.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    target_value: Mapped[str] = mapped_column(String(1024), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    checks: Mapped[list[Any]] = mapped_column(
        JSONType, default=list, nullable=False
    )  # dns, ct, search, github, reddit, news
    schedule: Mapped[str] = mapped_column(String(64), default="daily", nullable=False)  # daily|hourly|weekly|cron expr
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    keywords: Mapped[list[Any]] = mapped_column(JSONType, default=list, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    next_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    last_status: Mapped[str] = mapped_column(String(16), default="NEVER", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    baseline: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notify: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)  # {"telegram":true,...}


class Alert(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "alerts"
    display_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    monitor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("monitors.id", ondelete="SET NULL"), index=True)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), default="INFO", nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_label: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evidence.id", ondelete="SET NULL"))
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    delivered: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
