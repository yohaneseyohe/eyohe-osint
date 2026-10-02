"""Application errors with analyst-useful messages.

Every error carries a machine code, a human message, and optional structured detail (collector,
retry-after, impact) so the UI can show "GitHub collector failed: rate limit; retry in 42s"
instead of "Something went wrong".
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "detail": self.detail}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthenticated"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "forbidden"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


class ConfigurationError(AppError):
    """A connector/collector is not configured (e.g. missing API key). Never faked."""

    status_code = 503
    code = "not_configured"


class CollectorError(AppError):
    status_code = 502
    code = "collector_error"

    def __init__(
        self,
        collector: str,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        impact: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        d = dict(detail or {})
        d["collector"] = collector
        if retry_after_seconds is not None:
            d["retry_after_seconds"] = retry_after_seconds
        if impact:
            d["impact"] = impact
        super().__init__(f"{collector} collector failed: {message}", detail=d)
        self.collector = collector
        self.retry_after_seconds = retry_after_seconds


class UnsafeURLError(AppError):
    status_code = 400
    code = "unsafe_url"


class InvalidTransitionError(ConflictError):
    code = "invalid_transition"
