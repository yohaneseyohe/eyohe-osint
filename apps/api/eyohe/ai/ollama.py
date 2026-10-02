"""Ollama client: chat with optional tool schemas and strict JSON output.

All model calls go through here so timeouts, metrics, model selection and prompt hygiene are
uniform. The client never sees secrets and never executes anything itself.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from eyohe.core.config import get_settings
from eyohe.core.errors import ConfigurationError
from eyohe.core.logging import get_logger
from eyohe.core.metrics import ai_requests

log = get_logger("ollama")


class OllamaUnavailableError(ConfigurationError):
    code = "ollama_unavailable"


class OllamaClient:
    def __init__(self, model: str | None = None, timeout: float | None = None) -> None:
        s = get_settings()
        self.base = s.ollama_url.rstrip("/")
        self.model = model or s.ollama_model
        self.timeout = timeout or s.ollama_timeout_seconds
        self.num_ctx = s.ollama_num_ctx

    async def available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.get(f"{self.base}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{self.base}/api/tags")
            r.raise_for_status()
            return list(r.json().get("models", []))

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.1,
        purpose: str = "chat",
        think: bool | None = False,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": self.num_ctx, "num_predict": max_tokens},
        }
        if tools:
            payload["tools"] = tools
        if json_schema:
            payload["format"] = json_schema
        elif json_mode:
            payload["format"] = "json"
        if think is not None:
            payload["think"] = think
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                r = await c.post(f"{self.base}/api/chat", json=payload)
            if r.status_code == 404:
                ai_requests.labels(purpose=purpose, outcome="model_missing").inc()
                raise OllamaUnavailableError(f"Model '{self.model}' not found. Run: ollama pull {self.model}")
            if r.status_code == 400 and "think" in r.text and think is not None:
                payload.pop("think", None)
                async with httpx.AsyncClient(timeout=self.timeout) as c:
                    r = await c.post(f"{self.base}/api/chat", json=payload)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            ai_requests.labels(purpose=purpose, outcome="error").inc()
            raise OllamaUnavailableError(f"Ollama request failed: {type(exc).__name__}: {exc}") from exc
        ai_requests.labels(purpose=purpose, outcome="ok").inc()
        data: dict[str, Any] = r.json()
        log.info(
            "ollama_chat",
            purpose=purpose,
            ms=int((time.perf_counter() - t0) * 1000),
            model=self.model,
            eval_count=data.get("eval_count"),
        )
        return data

    async def chat_json(
        self,
        messages: list[dict[str, Any]],
        *,
        schema: dict[str, Any] | None = None,
        purpose: str = "json",
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> Any:
        data = await self.chat(
            messages,
            json_schema=schema,
            json_mode=schema is None,
            purpose=purpose,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = data.get("message", {}).get("content", "")
        return parse_json_loose(content)


def parse_json_loose(text: str) -> Any:
    """Parse JSON from a model reply, tolerating code fences and leading prose."""
    text = text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("model reply contained no JSON")
    depth = 0
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    for i in range(start, len(text)):
        if text[i] == opener:
            depth += 1
        elif text[i] == closer:
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unterminated JSON in model reply")
