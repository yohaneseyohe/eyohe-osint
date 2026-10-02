"""Request-id binding, structured access logs, security headers, and rate limiting."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from eyohe.core.config import get_settings
from eyohe.core.logging import get_logger

log = get_logger("http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = int((time.perf_counter() - start) * 1000)
        response.headers["x-request-id"] = request_id
        response.headers.setdefault("x-content-type-options", "nosniff")
        response.headers.setdefault("x-frame-options", "DENY")
        response.headers.setdefault("referrer-policy", "no-referrer")
        response.headers.setdefault("permissions-policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path.startswith("/api/") and not request.url.path.endswith("/events/stream"):
            log.info("request", method=request.method, path=request.url.path, status=response.status_code, ms=elapsed)
        return response


class SlidingWindowLimiter:
    """In-memory per-key sliding window. Fine for a single-workstation deployment; the arq/Redis
    variant is not needed until there are multiple API replicas."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window: float = 60.0) -> tuple[bool, int]:
        now = time.monotonic()
        q = self._hits[key]
        while q and q[0] < now - window:
            q.popleft()
        if len(q) >= limit:
            return False, int(window - (now - q[0])) + 1
        q.append(now)
        return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: SlidingWindowLimiter | None = None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.limiter = limiter or SlidingWindowLimiter()

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        settings = get_settings()
        path = request.url.path
        if not path.startswith("/api/") or path.endswith("/events/stream"):
            return await call_next(request)
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        is_auth = "/auth/login" in path or "/auth/setup" in path
        limit = settings.auth_rate_limit_per_minute if is_auth else settings.rate_limit_per_minute
        ok, retry = self.limiter.allow(f"{'auth' if is_auth else 'api'}:{ip}", limit)
        if not ok:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=429,
                content={
                    "code": "rate_limited",
                    "message": f"Too many requests. Retry in {retry} seconds.",
                    "detail": {"retry_after_seconds": retry},
                },
                headers={"retry-after": str(retry)},
            )
        return await call_next(request)
