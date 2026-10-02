"""Discovers collector plugins and exposes them to the planner, health checks and the API."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from eyohe.collectors.base import BaseCollector, CollectorHealth
from eyohe.core.enums import TargetType


class CollectorRegistry:
    def __init__(self) -> None:
        self._collectors: dict[str, BaseCollector] = {}
        self._loaded = False

    def register(self, collector: BaseCollector) -> None:
        self._collectors[collector.name] = collector

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        # Import side effects register the built-in plugins.
        from eyohe.collectors import plugins

        for c in plugins.BUILTIN_COLLECTORS:
            self.register(c)

    def get(self, name: str) -> BaseCollector | None:
        self._ensure_loaded()
        return self._collectors.get(name)

    def all(self) -> list[BaseCollector]:
        self._ensure_loaded()
        return list(self._collectors.values())

    def for_target(self, target_type: TargetType) -> list[BaseCollector]:
        return [c for c in self.all() if c.supports(target_type)]

    async def health_all(self, names: Iterable[str] | None = None) -> dict[str, CollectorHealth]:
        cols = self.all() if names is None else [c for c in self.all() if c.name in set(names)]

        async def one(c: BaseCollector) -> CollectorHealth:
            try:
                return await asyncio.wait_for(c.health_check(), timeout=6)
            except TimeoutError:
                return CollectorHealth(c.name, "OFFLINE", "health check timed out")
            except Exception as exc:
                return CollectorHealth(c.name, "OFFLINE", str(exc)[:200])

        results = await asyncio.gather(*(one(c) for c in cols))
        return {r.name: r for r in results}


collector_registry = CollectorRegistry()
