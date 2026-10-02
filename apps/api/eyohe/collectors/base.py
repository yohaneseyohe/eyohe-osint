"""Collector plugin interface.

Collectors never write to the database. They return :class:`CollectResult` containing normalized
items (sources, evidence candidates, entities, relationships, timeline events) with full
provenance, and the orchestrator persists them. This keeps collectors testable in isolation and
makes every piece of stored data traceable to a collector + URL + timestamp.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from eyohe.core.enums import EntityType, EvidenceType, RelationshipType, SourceType, TargetType


@dataclass
class CollectorHealth:
    name: str
    status: str  # ONLINE | OFFLINE | NOT_CONFIGURED | DEGRADED
    message: str = ""
    latency_ms: int | None = None


@dataclass
class SourceItem:
    url: str
    source_type: SourceType
    title: str = ""
    publisher: str = ""
    author: str = ""
    published_at: datetime | None = None
    tier: int = 5
    reliability_note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    # Optional captured content for a snapshot
    text_content: str = ""
    raw_content: bytes | None = None
    content_type: str = ""
    http_status: int | None = None
    final_url: str | None = None
    fetch_ms: int | None = None
    truncated: bool = False


@dataclass
class EntityItem:
    type: EntityType
    value: str
    label: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceItem:
    claim: str
    evidence_type: EvidenceType
    excerpt: str = ""
    context: str = ""
    source_url: str | None = None  # links to a SourceItem by url
    observed_at: datetime | None = None
    structured: dict[str, Any] = field(default_factory=dict)
    entities: list[EntityItem] = field(default_factory=list)
    collection_method: str = ""
    key: str = ""  # local key so relationships can reference this evidence


@dataclass
class RelationshipItem:
    source: EntityItem
    target: EntityItem
    type: RelationshipType
    rationale: str = ""
    evidence_keys: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class TimelineItem:
    occurred_at: datetime
    title: str
    description: str = ""
    precision: str = "day"
    event_kind: str = "OBSERVATION"
    evidence_key: str = ""
    entities: list[EntityItem] = field(default_factory=list)


@dataclass
class CollectResult:
    collector: str
    sources: list[SourceItem] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)
    entities: list[EntityItem] = field(default_factory=list)
    relationships: list[RelationshipItem] = field(default_factory=list)
    timeline: list[TimelineItem] = field(default_factory=list)
    discovered_targets: list[tuple[TargetType, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    raw_artifacts: list[tuple[str, bytes, str]] = field(default_factory=list)  # (name, bytes, mime)


@dataclass
class CollectContext:
    """Bounds and hooks the orchestrator hands to a collector."""

    case_id: str
    investigation_id: str | None = None
    task_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    max_results: int = 20
    emit: Any = None  # async callable(stage, message, data) for live feed events

    async def log(self, stage: str, message: str, **data: Any) -> None:
        if self.emit is not None:
            await self.emit(stage, message, data)


class BaseCollector(abc.ABC):
    name: str = "base"
    description: str = ""
    source_tier: int = 5
    supported_targets: frozenset[TargetType] = frozenset()
    requires_internet: bool = True
    stage: str = "COLLECT"  # label in the live feed

    def supports(self, target_type: TargetType) -> bool:
        return target_type in self.supported_targets

    @abc.abstractmethod
    async def health_check(self) -> CollectorHealth: ...

    @abc.abstractmethod
    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult: ...

    def normalize(self, raw: Any) -> Any:
        return raw

    def validate(self, item: Any) -> bool:
        return True
