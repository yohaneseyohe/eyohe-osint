"""URL canonicalization for deduplication and evidence identity."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "gclid",
    "fbclid",
    "msclkid",
    "dclid",
    "yclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "ref_url",
    "_hsenc",
    "_hsmi",
    "mkt_tok",
    "spm",
    "si",
    "feature",
}
DEFAULT_PORTS = {"http": "80", "https": "443"}
_MULTI_SLASH = re.compile(r"/{2,}")


def normalize_url(url: str) -> str:
    """Return a canonical form: lowercase scheme/host, no default port, no fragment,
    no tracking params, sorted query, no trailing slash (except root), IDNA host."""
    url = url.strip()
    if not url:
        return url
    if "://" not in url:
        url = "http://" + url
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    port = parts.port
    netloc = host
    if port and str(port) != DEFAULT_PORTS.get(scheme):
        netloc = f"{host}:{port}"
    path = _MULTI_SLASH.sub("/", unquote(parts.path or "/"))
    path = quote(path, safe="/:@!$&'()*+,;=-._~%")
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    query_pairs = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS
    ]
    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def registrable_domain(host_or_url: str) -> str:
    import tldextract

    ext = tldextract.extract(host_or_url)
    return ext.top_domain_under_public_suffix or ext.domain


def host_of(url: str) -> str:
    return (urlsplit(url if "://" in url else "http://" + url).hostname or "").lower()
