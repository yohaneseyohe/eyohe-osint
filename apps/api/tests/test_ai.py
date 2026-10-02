import httpx
import pytest
import respx

from eyohe.ai.intents import parse_intent
from eyohe.ai.ollama import parse_json_loose


def test_intents_map_to_structured_queries() -> None:
    assert parse_intent("Show all GitHub references.", "c1").filters == {"q": "github"}
    assert parse_intent("Show contradictory evidence", "c1").kind == "contradictions"
    i = parse_intent("Which sources mention this domain?", "c1")
    assert i.kind == "sources" and i.filters["q"] == "this domain"
    i = parse_intent("Find public references from 2025", "c1")
    assert i.kind == "evidence" and i.filters["year"] == 2025
    assert parse_intent("Generate a report as PDF", "c1").filters["format"] == "pdf"
    assert parse_intent("list all subdomains", "c1").filters["type"] == "DOMAIN"
    assert parse_intent("Find evidence supporting this relationship", "c1").filters["q"].startswith("this relationship")
    assert parse_intent("Is the admin of the site the same as the reddit user?", "c1").kind == "ask"


def test_parse_json_loose_handles_fences_and_think_tags() -> None:
    assert parse_json_loose('<think>hmm</think>```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_loose('Sure! Here it is: {"tasks": [{"x": "y"}]} thanks') == {"tasks": [{"x": "y"}]}
    with pytest.raises(ValueError):
        parse_json_loose("no json here")


@respx.mock
async def test_analyst_strips_hallucinated_citations(auth_client, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    r = await auth_client.post("/api/v1/cases", json={"name": "AI case", "targets": ["example.com"]})
    cid = r.json()["id"]
    r = await auth_client.post(
        f"/api/v1/cases/{cid}/evidence",
        json={
            "claim": "DNS A record for example.com points to 93.184.216.34",
            "evidence_type": "TECHNICAL_RECORD",
            "source_url": "https://example.com/",
            "excerpt": "93.184.216.34",
        },
    )
    ev_id = r.json()["display_id"]
    from eyohe.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ollama_url", "http://ollama.test:11434")
    respx.get("http://ollama.test:11434/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "qwen3:8b"}]})
    )
    respx.post("http://ollama.test:11434/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": f"The domain resolves to 93.184.216.34 [{ev_id}]. It was registered in 1995 [EYO-EV-999999].",
                }
            },
        )
    )
    r = await auth_client.post(
        "/api/v1/ai/query", json={"case_id": cid, "question": "What IP does example.com resolve to?", "mode": "ask"}
    )
    assert r.status_code == 200, r.text
    ans = r.json()["answer"]
    assert ev_id in [c["ref"] for c in ans["citations"]]
    assert "EYO-EV-999999" not in ans["answer"] and "unverified reference removed" in ans["answer"]
    # Routed intents don't call the model
    r = await auth_client.post("/api/v1/ai/query", json={"case_id": cid, "question": "show contradictory evidence"})
    assert r.json()["intent"]["kind"] == "contradictions" and "answer" not in r.json()


async def test_analyst_offline_says_not_found_without_model(auth_client) -> None:  # type: ignore[no-untyped-def]
    r = await auth_client.post("/api/v1/cases", json={"name": "Empty AI case", "targets": ["nothing-here.example"]})
    cid = r.json()["id"]
    r = await auth_client.post("/api/v1/ai/query", json={"case_id": cid, "question": "who owns this?", "mode": "ask"})
    assert r.status_code == 200 and r.json()["answer"]["answer"].startswith("Not found")


async def test_create_evidence_tool_rejects_unquoted_excerpt(auth_client) -> None:  # type: ignore[no-untyped-def]
    import uuid

    from eyohe.ai.tools import CreateEvidenceIn, ToolRuntime, t_create_evidence
    from eyohe.core.db import get_session_factory
    from eyohe.models.cases import Case, Target
    from eyohe.models.investigations import Investigation, InvestigationTask
    from eyohe.orchestrator.executors import RunContext

    r = await auth_client.post("/api/v1/cases", json={"name": "Tool guard", "targets": ["example.com"]})
    cid = uuid.UUID(r.json()["id"])
    async with get_session_factory()() as db:
        case = await db.get(Case, cid)
        target = (await db.execute(__import__("sqlalchemy").select(Target).where(Target.case_id == cid))).scalar_one()
        inv = Investigation(display_id="EYO-INV-T00001", case_id=cid, name="t", stats={"target_id": str(target.id)})
        db.add(inv)
        await db.flush()
        task = InvestigationTask(investigation_id=inv.id, order=0, task_type="research_agent", title="t")
        db.add(task)
        await db.flush()
        ctx = RunContext(session=db, investigation=inv, case=case, target=target)  # type: ignore[arg-type]
        rt = ToolRuntime(ctx=ctx, task=task)
        rt.fetched_text["https://example.com/about"] = "Acme Example Labs operates this website since 2019."
        rt.allow(["https://example.com/about"])
        out = await t_create_evidence(
            rt, CreateEvidenceIn(source_url="https://example.com/about", claim="x", excerpt="founded in 2010 by Jane")
        )
        assert "error" in out and "verbatim" in out["error"]
        out = await t_create_evidence(
            rt,
            CreateEvidenceIn(
                source_url="https://example.com/about",
                claim="Acme Example Labs operates the website",
                excerpt="Acme Example Labs operates this website",
            ),
        )
        assert out["evidence_id"].startswith("EYO-EV-")
        out = await t_create_evidence(
            rt, CreateEvidenceIn(source_url="https://never-fetched.example/", claim="x", excerpt="y")
        )
        assert "not fetched" in out["error"]
