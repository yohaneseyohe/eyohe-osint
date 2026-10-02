import httpx
import pytest
import respx

from eyohe.collectors.base import CollectContext
from eyohe.collectors.registry import collector_registry
from eyohe.core.enums import EntityType, EvidenceType, RelationshipType, TargetType


def ctx() -> CollectContext:
    return CollectContext(case_id="00000000-0000-0000-0000-000000000000", max_results=10)


def test_registry_lists_builtin_collectors() -> None:
    names = {c.name for c in collector_registry.all()}
    assert {"dns", "rdap", "ct_logs", "ip_info", "web_fetch", "wayback", "github", "reddit", "social_profiles"} <= names
    assert {c.name for c in collector_registry.for_target(TargetType.DOMAIN)} >= {
        "dns",
        "rdap",
        "ct_logs",
        "web_fetch",
        "wayback",
    }


@respx.mock
async def test_rdap_domain_produces_timeline_and_registrar(monkeypatch: pytest.MonkeyPatch) -> None:
    import eyohe.core.netsafety as ns

    async def fake_resolve(host: str, *, allow_private=None):  # type: ignore[no-untyped-def]
        return ["93.184.216.34"]

    monkeypatch.setattr(ns, "resolve_and_validate", fake_resolve)
    respx.get("https://rdap.org/domain/example.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "handle": "EX-1",
                "status": ["client transfer prohibited"],
                "events": [
                    {"eventAction": "registration", "eventDate": "1995-08-14T04:00:00Z"},
                    {"eventAction": "expiration", "eventDate": "2026-08-13T04:00:00Z"},
                ],
                "nameservers": [{"ldhName": "A.IANA-SERVERS.NET"}, {"ldhName": "B.IANA-SERVERS.NET"}],
                "entities": [
                    {
                        "roles": ["registrar"],
                        "handle": "376",
                        "vcardArray": ["vcard", [["fn", {}, "text", "RESERVED-Internet Assigned Numbers Authority"]]],
                    }
                ],
            },
        )
    )
    col = collector_registry.get("rdap")
    assert col is not None
    res = await col.collect(ctx(), TargetType.DOMAIN, "example.com")
    assert res.summary["registrar"].startswith("RESERVED")
    assert {t.event_kind for t in res.timeline} == {"REGISTRATION"}
    assert any(r.type == RelationshipType.REGISTERED_BY for r in res.relationships)
    assert any(r.type == RelationshipType.USES_NAMESERVER for r in res.relationships)
    assert res.evidence[0].evidence_type == EvidenceType.TECHNICAL_RECORD


@respx.mock
async def test_ct_logs_extracts_subdomains(monkeypatch: pytest.MonkeyPatch) -> None:
    import eyohe.core.netsafety as ns

    async def fake_resolve(host: str, *, allow_private=None):  # type: ignore[no-untyped-def]
        return ["1.1.1.1"]

    monkeypatch.setattr(ns, "resolve_and_validate", fake_resolve)
    respx.get(url__startswith="https://crt.sh/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "issuer_name": "C=US, O=Let's Encrypt, CN=R3",
                    "name_value": "www.example.com\nexample.com",
                    "not_before": "2024-01-01T00:00:00",
                    "not_after": "2024-04-01T00:00:00",
                },
                {
                    "issuer_name": "C=US, O=DigiCert",
                    "name_value": "api.example.com",
                    "not_before": "2023-06-01T00:00:00",
                    "not_after": "2024-06-01T00:00:00",
                },
                {
                    "issuer_name": "x",
                    "name_value": "notrelated.org",
                    "not_before": "2023-06-01T00:00:00",
                    "not_after": "2024-06-01T00:00:00",
                },
            ],
        )
    )
    col = collector_registry.get("ct_logs")
    assert col is not None
    res = await col.collect(ctx(), TargetType.DOMAIN, "example.com")
    assert res.summary["subdomains"] == 2
    subs = {r.source.value for r in res.relationships if r.type == RelationshipType.SUBDOMAIN_OF}
    assert subs == {"www.example.com", "api.example.com"}
    assert res.timeline and res.timeline[0].occurred_at.year == 2023


@respx.mock
async def test_github_redacts_secrets_and_handles_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    import eyohe.core.netsafety as ns
    from eyohe.core.config import get_settings

    async def fake_resolve(host: str, *, allow_private=None):  # type: ignore[no-untyped-def]
        return ["140.82.112.5"]

    monkeypatch.setattr(ns, "resolve_and_validate", fake_resolve)
    monkeypatch.setattr(get_settings(), "github_token", "ghp_testtoken_not_real_0000000000000000")
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=httpx.Response(
            200,
            json={
                "total_count": 1,
                "items": [
                    {
                        "full_name": "acme/site",
                        "html_url": "https://github.com/acme/site",
                        "description": "Site for example.com key=ghp_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE",
                        "stargazers_count": 3,
                        "language": "TypeScript",
                        "created_at": "2024-11-03T00:00:00Z",
                        "pushed_at": "2025-01-01T00:00:00Z",
                        "owner": {"login": "acme", "html_url": "https://github.com/acme"},
                        "topics": [],
                    }
                ],
            },
        )
    )
    respx.get("https://api.github.com/search/code").mock(
        return_value=httpx.Response(
            200,
            json={
                "total_count": 1,
                "items": [
                    {
                        "html_url": "https://github.com/acme/site/blob/main/.env.example",
                        "path": ".env.example",
                        "repository": {"full_name": "acme/site"},
                        "text_matches": [{"fragment": "API_URL=https://example.com\nAWS_KEY=AKIAFAKEFAKEFAKEFAKE"}],
                    }
                ],
            },
        )
    )
    col = collector_registry.get("github")
    assert col is not None
    res = await col.collect(ctx(), TargetType.DOMAIN, "example.com")
    blob = " ".join(e.claim + e.excerpt for e in res.evidence) + " ".join(s.text_content for s in res.sources)
    assert "ghp_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE" not in blob and "AKIAFAKEFAKEFAKEFAKE" not in blob
    assert any("redacted" in e.excerpt.lower() for e in res.evidence)
    assert res.summary["repositories"] == 1 and res.summary["code_hits"] == 1

    respx.get("https://api.github.com/search/repositories").mock(
        return_value=httpx.Response(403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "9999999999"})
    )
    from eyohe.core.errors import CollectorError

    with pytest.raises(CollectorError) as exc:
        await col.collect(ctx(), TargetType.DOMAIN, "other.com")
    assert exc.value.retry_after_seconds and "rate limit" in exc.value.message


@respx.mock
async def test_reddit_posts_are_public_statements_not_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    import eyohe.core.netsafety as ns

    async def fake_resolve(host: str, *, allow_private=None):  # type: ignore[no-untyped-def]
        return ["151.101.1.140"]

    monkeypatch.setattr(ns, "resolve_and_validate", fake_resolve)
    respx.get("https://www.reddit.com/search.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "children": [
                        {
                            "data": {
                                "id": "abc",
                                "permalink": "/r/netsec/comments/abc/example_com_scam/",
                                "title": "example.com is a scam, they stole my data",
                                "selftext": "details",
                                "author": "angry_user",
                                "subreddit": "netsec",
                                "created_utc": 1745280000,
                                "score": 10,
                                "num_comments": 2,
                            }
                        },
                        {
                            "data": {
                                "id": "def",
                                "permalink": "/r/webdev/comments/def/nice_site/",
                                "title": "Nice design on example.com",
                                "selftext": "",
                                "author": "dev1",
                                "subreddit": "webdev",
                                "created_utc": 1745380000,
                                "score": 1,
                                "num_comments": 0,
                            }
                        },
                    ]
                }
            },
        )
    )
    col = collector_registry.get("reddit")
    assert col is not None
    res = await col.collect(ctx(), TargetType.DOMAIN, "example.com")
    types = {e.structured["post_id"]: e.evidence_type for e in res.evidence}
    assert types["abc"] == EvidenceType.ALLEGATION and types["def"] == EvidenceType.PUBLIC_STATEMENT
    assert res.evidence[0].claim.startswith(
        "According to a Reddit post in r/netsec published on 2025-04-22, a user identified as u/angry_user alleged"
    )
    assert all(s.tier == 4 for s in res.sources)


def test_html_to_text_and_document_extraction() -> None:
    from eyohe.collectors.web_collector import html_to_text
    from eyohe.enrichment.documents import extract_document

    title, text, meta = html_to_text(
        "<html><head><title>Acme</title><meta name='description' content='desc'><script>x()</script></head><body><h1>Hi</h1><p>there</p></body></html>"
    )
    assert title == "Acme" and "x()" not in text and "Hi" in text and meta["description"] == "desc"
    info = extract_document(b"plain text body", "text/plain")
    assert info.text == "plain text body"
    info = extract_document(b"not a pdf", "application/pdf")
    assert info.warnings


async def test_dns_collector_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    col = collector_registry.get("dns")
    assert col is not None

    async def fake_query(name: str, rtype: str) -> list[str]:
        table = {
            "A": ["93.184.216.34"],
            "MX": ["10 mail.example.com"],
            "NS": ["a.iana-servers.net"],
            "TXT": ["v=spf1 include:_spf.example.net -all"],
        }
        if name.startswith("_dmarc"):
            return ["v=DMARC1; p=reject"]
        return table.get(rtype, [])

    monkeypatch.setattr(col, "_query", fake_query)
    res = await col.collect(ctx(), TargetType.DOMAIN, "example.com")
    rtypes = {e.structured["record_type"] for e in res.evidence}
    assert {"A", "MX", "NS", "TXT", "DMARC"} <= rtypes
    rel_types = {r.type for r in res.relationships}
    assert {
        RelationshipType.RESOLVES_TO,
        RelationshipType.USES_MAIL_SERVER,
        RelationshipType.USES_NAMESERVER,
    } <= rel_types
    assert any(
        e.type == EntityType.DOMAIN and e.value == "_spf.example.net" for ev in res.evidence for e in ev.entities
    )
    assert (TargetType.IP, "93.184.216.34") in res.discovered_targets
