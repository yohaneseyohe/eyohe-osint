from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from eyohe.core.security import sha256_text
from eyohe.core.urlnorm import normalize_url, registrable_domain


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str = ""
    engine: str = ""
    provider: str = ""
    published_at: datetime | None = None
    score: float = 0.0
    category: str = "general"
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def canonical_url(self) -> str:
        return normalize_url(self.url)

    @property
    def domain(self) -> str:
        return registrable_domain(self.url)

    @property
    def result_hash(self) -> str:
        return sha256_text(f"{self.canonical_url}|{self.title.strip().lower()}")


@dataclass
class SearchResponse:
    query: str
    provider: str
    hits: list[SearchHit]
    cache_hit: bool = False
    elapsed_ms: int = 0
    warnings: list[str] = field(default_factory=list)
