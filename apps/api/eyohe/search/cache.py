"""Query result cache: Redis when reachable, otherwise an in-process TTL cache."""

from __future__ import annotations

import time
from typing import Any

import orjson

from eyohe.core.config import get_settings
from eyohe.core.logging import get_logger

log = get_logger("search.cache")


class QueryCache:
    def __init__(self, ttl_seconds: int = 6 * 3600, max_items: int = 500) -> None:
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._mem: dict[str, tuple[float, Any]] = {}
        self._redis: Any = None
        self._checked = False

    async def _r(self) -> Any:
        if self._checked:
            return self._redis
        self._checked = True
        if get_settings().eyohe_env == "test":
            return None
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1)  # type: ignore[no-untyped-call]
            await r.ping()
            self._redis = r
        except Exception:
            self._redis = None
        return self._redis

    async def get(self, key: str) -> Any | None:
        r = await self._r()
        if r is not None:
            try:
                raw = await r.get(f"eyohe:q:{key}")
                return orjson.loads(raw) if raw else None
            except Exception as exc:
                log.debug("redis_cache_get_failed", error=str(exc))
        item = self._mem.get(key)
        if item and item[0] > time.monotonic():
            return item[1]
        self._mem.pop(key, None)
        return None

    async def set(self, key: str, value: Any) -> None:
        r = await self._r()
        if r is not None:
            try:
                await r.set(f"eyohe:q:{key}", orjson.dumps(value, default=str), ex=self.ttl)
                return
            except Exception as exc:
                log.debug("redis_cache_set_failed", error=str(exc))
        if len(self._mem) >= self.max_items:
            oldest = min(self._mem, key=lambda k: self._mem[k][0])
            self._mem.pop(oldest, None)
        self._mem[key] = (time.monotonic() + self.ttl, value)


query_cache = QueryCache()
