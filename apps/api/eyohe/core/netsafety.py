"""SSRF-safe outbound HTTP.

All collectors fetch through :class:`SafeHttpClient`. Before every request (and every redirect
hop) the destination is validated: only http/https, no embedded credentials, no literal or
DNS-resolved private/loopback/link-local/multicast/reserved addresses, no cloud-metadata hosts,
no internal TLDs. Response size is capped. ``ALLOW_PRIVATE_NETWORK_FETCH`` disables the address
checks for explicit local testing and is logged loudly when used.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from eyohe.core.config import get_settings
from eyohe.core.errors import UnsafeURLError
from eyohe.core.logging import get_logger

log = get_logger("netsafety")

BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "169.254.169.254",
    "fd00:ec2::254",
    "100.100.100.200",  # Alibaba metadata
}
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home", ".corp", ".intranet")


def _ip_is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("100.64.0.0/10"))
        or (isinstance(ip, ipaddress.IPv6Address) and ip.is_site_local)
    )


def validate_url_syntax(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError(f"Only http(s) URLs may be fetched (got scheme '{parts.scheme or 'none'}').")
    if not parts.hostname:
        raise UnsafeURLError("URL has no host.")
    if parts.username or parts.password:
        raise UnsafeURLError("URLs with embedded credentials are not allowed.")
    if len(url) > 4096:
        raise UnsafeURLError("URL too long.")
    return parts.hostname.lower().rstrip(".")


def validate_host(host: str, *, allow_private: bool | None = None) -> None:
    settings = get_settings()
    if allow_private is None:
        allow_private = settings.allow_private_network_fetch
    if host in BLOCKED_HOSTS or host.endswith(BLOCKED_SUFFIXES):
        if not allow_private:
            raise UnsafeURLError(f"Host '{host}' is internal/metadata and blocked.")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return
    if not allow_private and not _ip_is_public(ip):
        raise UnsafeURLError(f"Address {ip} is not a public address.")


async def resolve_and_validate(host: str, *, allow_private: bool | None = None) -> list[str]:
    """Resolve host and verify every address is public. Returns the address list."""
    settings = get_settings()
    if allow_private is None:
        allow_private = settings.allow_private_network_fetch
    validate_host(host, allow_private=allow_private)
    try:
        ipaddress.ip_address(host.strip("[]"))
        return [host]
    except ValueError:
        pass
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(loop.getaddrinfo(host, None, type=socket.SOCK_STREAM), timeout=10)
    except (socket.gaierror, TimeoutError) as exc:
        raise UnsafeURLError(f"Could not resolve host '{host}'.") from exc
    addrs = sorted({str(info[4][0]) for info in infos})
    if not addrs:
        raise UnsafeURLError(f"Host '{host}' has no addresses.")
    if not allow_private:
        for a in addrs:
            if not _ip_is_public(ipaddress.ip_address(a)):
                raise UnsafeURLError(f"Host '{host}' resolves to non-public address {a}; blocked.")
    return addrs


async def validate_url(url: str) -> str:
    host = validate_url_syntax(url)
    await resolve_and_validate(host)
    return host


@dataclass
class HostRateLimiter:
    """Simple per-host minimum interval limiter so collectors stay polite."""

    min_interval: float = 1.0
    _last: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    _locks: dict[str, asyncio.Lock] = field(default_factory=lambda: defaultdict(asyncio.Lock))

    async def wait(self, host: str) -> None:
        async with self._locks[host]:
            now = time.monotonic()
            delta = now - self._last[host]
            if delta < self.min_interval:
                await asyncio.sleep(self.min_interval - delta)
            self._last[host] = time.monotonic()


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    headers: dict[str, str]
    content: bytes
    content_type: str
    elapsed_ms: int
    truncated: bool = False

    @property
    def text(self) -> str:
        enc = "utf-8"
        ct = self.content_type
        if "charset=" in ct:
            enc = ct.split("charset=", 1)[1].split(";")[0].strip().strip('"') or "utf-8"
        try:
            return self.content.decode(enc, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")


class SafeHttpClient:
    """httpx wrapper enforcing SSRF rules, size caps, timeouts, and per-host rate limits."""

    def __init__(
        self,
        *,
        timeout: float | None = None,
        max_bytes: int | None = None,
        max_redirects: int = 5,
        min_interval: float = 0.5,
        headers: dict[str, str] | None = None,
    ) -> None:
        s = get_settings()
        self.timeout = timeout or s.request_timeout
        self.max_bytes = max_bytes or s.max_fetch_bytes
        self.max_redirects = max_redirects
        self.limiter = HostRateLimiter(min_interval=min_interval)
        self._headers = {"User-Agent": s.user_agent, "Accept": "*/*", **(headers or {})}
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=min(10.0, self.timeout)),
            follow_redirects=False,
            headers=self._headers,
            http2=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def __aenter__(self) -> SafeHttpClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json: Any = None,
        data: Any = None,
        allow_private: bool | None = None,
    ) -> FetchResult:
        current = url
        hops = 0
        start = time.monotonic()
        while True:
            host = validate_url_syntax(current)
            await resolve_and_validate(host, allow_private=allow_private)
            if allow_private:
                log.warning("private_network_fetch", url=current)
            await self.limiter.wait(host)
            req = self._client.build_request(
                method, current, params=params if hops == 0 else None, headers=headers, json=json, data=data
            )
            resp = await self._client.send(req, stream=True)
            try:
                if resp.is_redirect and hops < self.max_redirects:
                    location = resp.headers.get("location")
                    if not location:
                        raise UnsafeURLError("Redirect without Location header.")
                    current = str(httpx.URL(current).join(location))
                    hops += 1
                    method = "GET" if resp.status_code in (301, 302, 303) else method
                    json = data = None
                    continue
                if resp.is_redirect:
                    raise UnsafeURLError("Too many redirects.")
                chunks: list[bytes] = []
                size = 0
                truncated = False
                async for chunk in resp.aiter_bytes():
                    size += len(chunk)
                    if size > self.max_bytes:
                        chunks.append(chunk[: max(0, self.max_bytes - (size - len(chunk)))])
                        truncated = True
                        break
                    chunks.append(chunk)
                content = b"".join(chunks)
            finally:
                await resp.aclose()
            return FetchResult(
                url=url,
                final_url=current,
                status_code=resp.status_code,
                headers={k.lower(): v for k, v in resp.headers.items()},
                content=content,
                content_type=resp.headers.get("content-type", ""),
                elapsed_ms=int((time.monotonic() - start) * 1000),
                truncated=truncated,
            )

    async def get(self, url: str, **kw: Any) -> FetchResult:
        return await self.request("GET", url, **kw)

    async def post(self, url: str, **kw: Any) -> FetchResult:
        return await self.request("POST", url, **kw)

    async def get_json(self, url: str, **kw: Any) -> Any:
        import orjson

        res = await self.get(url, **kw)
        if res.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {res.status_code} for {url}",
                request=httpx.Request("GET", url),
                response=httpx.Response(res.status_code, content=res.content),
            )
        return orjson.loads(res.content)
