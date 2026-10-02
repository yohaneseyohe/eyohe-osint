"""GitHub public API: users/orgs, repositories, repository search, and (with a token) code search.
Secrets found in snippets are redacted before storage; the UI never sees them."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import orjson
from dateutil import parser as dateparser

from eyohe.collectors.base import (
    BaseCollector,
    CollectContext,
    CollectorHealth,
    CollectResult,
    EntityItem,
    EvidenceItem,
    RelationshipItem,
    SourceItem,
    TimelineItem,
)
from eyohe.core.config import get_settings
from eyohe.core.enums import EntityType, EvidenceType, RelationshipType, SourceType, TargetType
from eyohe.core.errors import CollectorError
from eyohe.core.logging import contains_secret, redact_text
from eyohe.core.netsafety import SafeHttpClient

API = "https://api.github.com"


def _dt(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        d = dateparser.parse(str(v))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except (ValueError, TypeError, OverflowError):
        return None


class GitHubCollector(BaseCollector):
    name = "github"
    description = "GitHub public users, organisations, repositories and references (code search needs GITHUB_TOKEN)"
    source_tier = 3
    supported_targets = frozenset(
        {
            TargetType.DOMAIN,
            TargetType.USERNAME,
            TargetType.SOCIAL_ACCOUNT,
            TargetType.ORGANIZATION,
            TargetType.COMPANY,
            TargetType.EMAIL,
            TargetType.IP,
            TargetType.CRYPTO_ADDRESS,
            TargetType.PERSON,
        }
    )
    stage = "GITHUB"

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        tok = get_settings().github_token
        if tok:
            h["Authorization"] = f"Bearer {tok}"
        return h

    async def health_check(self) -> CollectorHealth:
        t = time.perf_counter()
        try:
            async with SafeHttpClient(timeout=6) as c:
                r = await c.get(f"{API}/rate_limit", headers=self._headers())
            data = orjson.loads(r.content) if r.status_code == 200 else {}
            core = data.get("resources", {}).get("core", {})
            auth = (
                "authenticated"
                if get_settings().github_token
                else "unauthenticated (60 req/h; set GITHUB_TOKEN for code search)"
            )
            return CollectorHealth(
                self.name,
                "ONLINE" if r.status_code == 200 else "DEGRADED",
                f"{auth}; remaining {core.get('remaining', '?')}/{core.get('limit', '?')}",
                int((time.perf_counter() - t) * 1000),
            )
        except Exception as exc:
            return CollectorHealth(self.name, "OFFLINE", f"api.github.com unreachable: {type(exc).__name__}")

    async def _get(self, c: SafeHttpClient, path: str, params: dict[str, Any] | None = None) -> Any:
        r = await c.get(f"{API}{path}", params=params, headers=self._headers())
        if r.status_code in (403, 429) and r.headers.get("x-ratelimit-remaining") == "0":
            reset = int(r.headers.get("x-ratelimit-reset", "0") or 0)
            wait = max(1, reset - int(time.time())) if reset else 60
            raise CollectorError(
                self.name,
                "API rate limit reached"
                + ("" if get_settings().github_token else " (unauthenticated: 60 requests/hour; add GITHUB_TOKEN)"),
                retry_after_seconds=wait,
                impact="GitHub task incomplete",
            )
        if r.status_code == 404:
            return None
        if r.status_code == 422:
            return {"items": [], "total_count": 0}
        if r.status_code >= 400:
            raise CollectorError(self.name, f"GitHub API HTTP {r.status_code} for {path}")
        return orjson.loads(r.content)

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        res = CollectResult(collector=self.name)
        handle = ctx.params.get("handle") or (
            value.split(":", 1)[1] if target_type == TargetType.SOCIAL_ACCOUNT and value.startswith("github:") else None
        )
        async with SafeHttpClient(timeout=25, min_interval=0.8) as c:
            if target_type in (TargetType.USERNAME, TargetType.SOCIAL_ACCOUNT):
                await self._profile(ctx, c, res, handle or value.split(":", 1)[-1])
            await self._search(ctx, c, res, target_type, value)
        res.summary.setdefault("records", len(res.evidence))
        await ctx.log(
            "GITHUB",
            f"GitHub: {res.summary.get('repositories', 0)} repositories, {res.summary.get('code_hits', 0)} code references"
            + (" (profile found)" if res.summary.get("profile") else ""),
            **res.summary,
        )
        return res

    async def _profile(self, ctx: CollectContext, c: SafeHttpClient, res: CollectResult, handle: str) -> None:
        user = await self._get(c, f"/users/{handle}")
        if not user:
            res.summary["profile"] = False
            res.warnings.append(f"No public GitHub account named '{handle}' (not publicly verifiable).")
            return
        url = user.get("html_url", f"https://github.com/{handle}")
        acct = EntityItem(
            EntityType.SOCIAL_ACCOUNT,
            f"github:{user['login'].lower()}",
            label=f"{user['login']} (GitHub)",
            attributes={"platform": "github", "handle": user["login"], "url": url, "type": user.get("type")},
        )
        src = SourceItem(
            url=url,
            source_type=SourceType.CODE_REPOSITORY,
            title=f"GitHub profile: {user['login']}",
            publisher="GitHub",
            published_at=_dt(user.get("created_at")),
            tier=3,
            reliability_note="Platform API record; profile fields are self-declared by the account holder.",
            text_content=orjson.dumps(user).decode()[:20000],
            content_type="application/json",
            http_status=200,
            metadata={"login": user["login"], "type": user.get("type")},
        )
        res.sources.append(src)
        ents: list[EntityItem] = [acct]
        if user.get("name"):
            ents.append(
                EntityItem(
                    EntityType.PERSON if user.get("type") == "User" else EntityType.ORGANIZATION,
                    user["name"],
                    attributes={"from": "github profile name (self-declared)"},
                )
            )
        if user.get("blog"):
            blog = user["blog"] if "://" in user["blog"] else f"https://{user['blog']}"
            ents.append(EntityItem(EntityType.URL, blog))
            from eyohe.core.urlnorm import registrable_domain

            ents.append(EntityItem(EntityType.DOMAIN, registrable_domain(blog)))
        if user.get("email"):
            ents.append(EntityItem(EntityType.EMAIL, user["email"]))
        if user.get("company"):
            ents.append(
                EntityItem(
                    EntityType.ORGANIZATION,
                    user["company"].lstrip("@"),
                    attributes={"from": "github profile company (self-declared)"},
                )
            )
        if user.get("twitter_username"):
            ents.append(
                EntityItem(
                    EntityType.SOCIAL_ACCOUNT,
                    f"x:{user['twitter_username'].lower()}",
                    attributes={"platform": "x", "handle": user["twitter_username"]},
                )
            )
        if user.get("location"):
            ents.append(
                EntityItem(EntityType.LOCATION, user["location"], attributes={"from": "github profile (self-declared)"})
            )
        bio = (user.get("bio") or "").strip()
        claim = (
            f"Public GitHub account '{user['login']}' ({user.get('type')}) exists; created {str(user.get('created_at', ''))[:10]}; {user.get('public_repos', 0)} public repos, {user.get('followers', 0)} followers"
            + (f"; display name '{user['name']}'" if user.get("name") else "")
            + (f"; bio: {bio[:160]}" if bio else "")
        )
        res.evidence.append(
            EvidenceItem(
                claim=claim,
                evidence_type=EvidenceType.TECHNICAL_RECORD,
                excerpt=orjson.dumps(
                    {
                        k: user.get(k)
                        for k in (
                            "login",
                            "name",
                            "company",
                            "blog",
                            "location",
                            "bio",
                            "twitter_username",
                            "public_repos",
                            "followers",
                            "created_at",
                        )
                    }
                ).decode()[:1200],
                source_url=url,
                observed_at=_dt(user.get("created_at")),
                structured={
                    "profile": {
                        k: user.get(k)
                        for k in (
                            "login",
                            "type",
                            "name",
                            "company",
                            "blog",
                            "location",
                            "bio",
                            "twitter_username",
                            "public_repos",
                            "followers",
                            "created_at",
                            "updated_at",
                        )
                    }
                },
                entities=ents,
                collection_method="github_api_user",
                key="gh-profile",
            )
        )
        user_created = _dt(user.get("created_at"))
        if user_created:
            res.timeline.append(
                TimelineItem(
                    occurred_at=user_created,
                    title=f"GitHub account '{user['login']}' created",
                    description="From the GitHub API created_at field",
                    event_kind="ACCOUNT_CREATED",
                    evidence_key="gh-profile",
                    entities=[acct],
                )
            )
        for e in ents[1:]:
            rtype = (
                RelationshipType.LINKS_TO
                if e.type in (EntityType.URL, EntityType.SOCIAL_ACCOUNT)
                else RelationshipType.ASSOCIATED_WITH
            )
            res.relationships.append(
                RelationshipItem(
                    acct, e, rtype, rationale="self-declared on the public GitHub profile", evidence_keys=["gh-profile"]
                )
            )
        repos = (
            await self._get(c, f"/users/{handle}/repos", {"sort": "updated", "per_page": min(ctx.max_results, 30)})
            or []
        )
        for repo in repos:
            self._repo_item(res, repo, acct)
        res.summary["profile"] = True
        res.summary["repositories"] = len(repos)
        for e in ents:
            if e.type == EntityType.DOMAIN:
                res.discovered_targets.append((TargetType.DOMAIN, e.value))

    def _repo_item(self, res: CollectResult, repo: dict[str, Any], owner: EntityItem | None) -> None:
        full = repo.get("full_name", "")
        url = repo.get("html_url", f"https://github.com/{full}")
        repo_entity = EntityItem(
            EntityType.REPOSITORY,
            full,
            label=full,
            attributes={
                "platform": "github",
                "url": url,
                "stars": repo.get("stargazers_count"),
                "language": repo.get("language"),
            },
        )
        key = f"gh-repo-{full}"
        desc = redact_text(repo.get("description") or "")
        res.sources.append(
            SourceItem(
                url=url,
                source_type=SourceType.CODE_REPOSITORY,
                title=f"GitHub repository {full}",
                publisher="GitHub",
                published_at=_dt(repo.get("created_at")),
                tier=3,
                text_content=f"{full}\n{desc}\nhomepage: {repo.get('homepage') or ''}\ntopics: {', '.join(repo.get('topics', []))}",
                content_type="application/json",
                http_status=200,
                metadata={
                    "stars": repo.get("stargazers_count"),
                    "forks": repo.get("forks_count"),
                    "language": repo.get("language"),
                    "archived": repo.get("archived"),
                    "fork": repo.get("fork"),
                },
            )
        )
        ents = [repo_entity]
        if owner:
            ents.append(owner)
        if repo.get("homepage"):
            hp = repo["homepage"] if "://" in repo["homepage"] else f"https://{repo['homepage']}"
            ents.append(EntityItem(EntityType.URL, hp))
        res.evidence.append(
            EvidenceItem(
                claim=f"Public GitHub repository {full}"
                + (f": {desc[:160]}" if desc else "")
                + f" ({repo.get('stargazers_count', 0)} stars, {repo.get('language') or 'n/a'}, created {str(repo.get('created_at', ''))[:10]}, pushed {str(repo.get('pushed_at', ''))[:10]})",
                evidence_type=EvidenceType.TECHNICAL_RECORD,
                excerpt=desc[:500],
                source_url=url,
                observed_at=_dt(repo.get("created_at")),
                structured={
                    "full_name": full,
                    "stars": repo.get("stargazers_count"),
                    "language": repo.get("language"),
                    "homepage": repo.get("homepage"),
                    "topics": repo.get("topics", []),
                    "fork": repo.get("fork"),
                },
                entities=ents,
                collection_method="github_api_repo",
                key=key,
            )
        )
        if owner:
            res.relationships.append(
                RelationshipItem(
                    owner,
                    repo_entity,
                    RelationshipType.OWNS,
                    rationale="repository owner on GitHub",
                    evidence_keys=[key],
                )
            )
        repo_created = _dt(repo.get("created_at"))
        if repo_created:
            res.timeline.append(
                TimelineItem(
                    occurred_at=repo_created,
                    title=f"Repository {full} created",
                    event_kind="REPOSITORY_CREATED",
                    evidence_key=key,
                    entities=[repo_entity],
                )
            )

    async def _search(
        self, ctx: CollectContext, c: SafeHttpClient, res: CollectResult, target_type: TargetType, value: str
    ) -> None:
        term = value.split(":", 1)[-1] if target_type == TargetType.SOCIAL_ACCOUNT else value
        q = f'"{term}"' if " " in term or "." in term else term
        data = (
            await self._get(c, "/search/repositories", {"q": q, "per_page": min(ctx.max_results, 20), "sort": "stars"})
            or {}
        )
        items = data.get("items", [])
        for repo in items:
            owner = repo.get("owner") or {}
            owner_ent = (
                EntityItem(
                    EntityType.SOCIAL_ACCOUNT,
                    f"github:{owner.get('login', '').lower()}",
                    label=f"{owner.get('login')} (GitHub)",
                    attributes={"platform": "github", "handle": owner.get("login"), "url": owner.get("html_url")},
                )
                if owner.get("login")
                else None
            )
            self._repo_item(res, repo, owner_ent)
        res.summary["repositories"] = res.summary.get("repositories", 0) + len(items)
        res.summary["repository_search_total"] = data.get("total_count", 0)
        if get_settings().github_token and target_type in (
            TargetType.DOMAIN,
            TargetType.EMAIL,
            TargetType.IP,
            TargetType.CRYPTO_ADDRESS,
        ):
            code = await self._get(c, "/search/code", {"q": f'"{term}"', "per_page": min(ctx.max_results, 15)}) or {}
            hits = code.get("items", [])
            redacted = 0
            for h in hits:
                repo = h.get("repository", {})
                url = h.get("html_url", "")
                full = repo.get("full_name", "")
                frag = ""
                for m in h.get("text_matches", []) or []:
                    frag += (m.get("fragment") or "") + "\n"
                if contains_secret(frag) or contains_secret(h.get("path", "")):
                    redacted += 1
                    frag = "Potential secret detected — redacted."
                res.sources.append(
                    SourceItem(
                        url=url,
                        source_type=SourceType.CODE_REPOSITORY,
                        title=f"{full}: {h.get('path')}",
                        publisher="GitHub",
                        tier=3,
                        text_content=redact_text(frag)[:5000],
                        content_type="text/plain",
                        http_status=200,
                    )
                )
                res.evidence.append(
                    EvidenceItem(
                        claim=f"File {h.get('path')} in public repository {full} references '{term}'",
                        evidence_type=EvidenceType.TECHNICAL_RECORD,
                        excerpt=redact_text(frag)[:500],
                        source_url=url,
                        structured={
                            "repository": full,
                            "path": h.get("path"),
                            "redacted": frag.startswith("Potential secret"),
                        },
                        entities=[EntityItem(EntityType.REPOSITORY, full, attributes={"platform": "github"})],
                        collection_method="github_code_search",
                        key=f"gh-code-{url}",
                    )
                )
            res.summary["code_hits"] = len(hits)
            if redacted:
                res.warnings.append(f"{redacted} code match(es) contained potential secrets and were redacted.")
        elif not get_settings().github_token and target_type in (TargetType.DOMAIN, TargetType.EMAIL):
            res.warnings.append("GitHub code search skipped: requires GITHUB_TOKEN (public API restriction).")
