"""Human-readable display identifiers (EYO-CASE-000001, EYO-EV-000042, ...).

A dedicated counter table keeps this portable between PostgreSQL and SQLite and makes the
identifiers stable across exports/imports. UUIDs remain the primary keys.
"""

from __future__ import annotations

from sqlalchemy import Integer, String, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from eyohe.core.db import Base

PREFIXES = {
    "case": "EYO-CASE",
    "evidence": "EYO-EV",
    "finding": "EYO-FND",
    "entity": "EYO-ENT",
    "source": "EYO-SRC",
    "investigation": "EYO-INV",
    "report": "EYO-RPT",
    "relationship": "EYO-REL",
    "monitor": "EYO-MON",
    "alert": "EYO-ALR",
}


class IdSequence(Base):
    __tablename__ = "id_sequences"
    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


async def next_display_id(session: AsyncSession, kind: str) -> str:
    prefix = PREFIXES[kind]
    # Atomic increment; the row is created lazily the first time a kind is used.
    result = await session.execute(
        update(IdSequence).where(IdSequence.name == kind).values(value=IdSequence.value + 1).returning(IdSequence.value)
    )
    value = result.scalar_one_or_none()
    if value is None:
        session.add(IdSequence(name=kind, value=1))
        await session.flush()
        value = 1
        # Re-read in case of a concurrent insert that won the race.
        row = (await session.execute(select(IdSequence.value).where(IdSequence.name == kind))).scalar_one()
        value = row
    return f"{prefix}-{value:06d}"
