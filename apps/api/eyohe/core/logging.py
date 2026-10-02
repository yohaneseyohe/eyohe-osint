"""Structured JSON logging with secret redaction and request/case/task context binding."""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

from eyohe.core.config import get_settings

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret|authorization)([\"'=:\s]+)([^\s\"',;]+)"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
]


def redact_text(text: str) -> str:
    """Mask secret-looking material. Used for logs and for collected content before storage."""
    out = text
    out = _SECRET_PATTERNS[0].sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", out)
    for pat in _SECRET_PATTERNS[1:]:
        out = pat.sub("[REDACTED]", out)
    return out


def contains_secret(text: str) -> bool:
    return any(p.search(text) for p in _SECRET_PATTERNS[1:])


def _redact_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for k, v in list(event_dict.items()):
        if isinstance(v, str):
            event_dict[k] = redact_text(v)
        if k.lower() in {"password", "token", "api_key", "secret", "authorization", "cookie"}:
            event_dict[k] = "[REDACTED]"
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer]
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(service: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(service=service)  # type: ignore[no-any-return]
