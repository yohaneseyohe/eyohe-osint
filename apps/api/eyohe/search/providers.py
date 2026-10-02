"""Search provider connectors (Phase 3 fills in the implementations).

Each provider is either *configured* (usable) or raises ``ConfigurationError``; nothing ever
returns fabricated results.
"""

from __future__ import annotations

import time

import httpx

from eyohe.core.config import get_settings
from eyohe.services.health import ComponentHealth


async def provider_health() -> ComponentHealth:
    s = get_settings()
    configured: list[str] = []
    problems: list[str] = []
    t = time.perf_counter()
    for name in s.search_provider_list:
        if name == "searxng":
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    r = await client.get(f"{s.searxng_url.rstrip('/')}/search", params={"q": "eyohe", "format": "json"})
                if r.status_code == 200:
                    configured.append("searxng")
                elif r.status_code == 403:
                    problems.append("searxng: JSON format disabled (enable 'json' in settings.yml formats)")
                else:
                    problems.append(f"searxng: HTTP {r.status_code}")
            except Exception as exc:
                problems.append(f"searxng unreachable at {s.searxng_url} ({type(exc).__name__})")
        elif name == "brave":
            (configured if s.brave_api_key else problems).append(
                "brave" if s.brave_api_key else "brave: BRAVE_API_KEY missing"
            )
        elif name == "serper":
            (configured if s.serper_api_key else problems).append(
                "serper" if s.serper_api_key else "serper: SERPER_API_KEY missing"
            )
        elif name == "tavily":
            (configured if s.tavily_api_key else problems).append(
                "tavily" if s.tavily_api_key else "tavily: TAVILY_API_KEY missing"
            )
        else:
            problems.append(f"unknown provider '{name}'")
    status = "ONLINE" if configured else ("NOT_CONFIGURED" if not s.search_provider_list else "OFFLINE")
    msg = f"providers ready: {', '.join(configured)}" if configured else "; ".join(problems) or "no providers"
    if configured and problems:
        status = "DEGRADED"
        msg += " | " + "; ".join(problems)
    return ComponentHealth(
        "search",
        status,
        msg,
        int((time.perf_counter() - t) * 1000),
        {"configured": configured, "problems": problems},
    )
