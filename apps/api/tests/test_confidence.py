import uuid
from datetime import UTC, datetime

from eyohe.core.enums import Confidence, EvidenceType, ReviewState
from eyohe.models.evidence import Evidence
from eyohe.verification.confidence import assess


def _ev(
    tier: int, domain: str, etype: EvidenceType = EvidenceType.DIRECT_STATEMENT, review: str = "PENDING"
) -> Evidence:
    e = Evidence(
        id=uuid.uuid4(),
        display_id=f"EYO-EV-{uuid.uuid4().hex[:6]}",
        case_id=uuid.uuid4(),
        evidence_type=str(etype),
        claim="c",
        collector="t",
        collected_at=datetime.now(UTC),
        confidence="UNVERIFIED",
        review_state=review,
        content_hash="x",
        structured={"tier": tier, "url": f"https://{domain}/p"},
        entity_ids=[],
    )
    return e


def test_no_evidence_is_unverified() -> None:
    assert assess([]).label == Confidence.UNVERIFIED


def test_single_official_source_is_supported() -> None:
    r = assess([_ev(1, "example.com")])
    assert r.label == Confidence.SUPPORTED and r.best_tier == 1


def test_single_forum_is_possible() -> None:
    assert assess([_ev(4, "reddit.com")]).label == Confidence.POSSIBLE


def test_two_independent_sources_corroborate() -> None:
    r = assess([_ev(3, "crt.sh"), _ev(4, "reddit.com")])
    assert r.label == Confidence.CORROBORATED and r.independent_sources == 2


def test_same_domain_twice_is_not_corroborated() -> None:
    r = assess([_ev(4, "reddit.com"), _ev(4, "reddit.com")])
    assert r.label == Confidence.SUPPORTED and r.independent_sources == 1


def test_contradiction_from_better_source_wins() -> None:
    a, b = _ev(4, "reddit.com"), _ev(1, "example.com")
    r = assess([a, b], {a.id: "supports", b.id: "contradicts"})
    assert r.label == Confidence.CONTRADICTED


def test_only_inference_is_inference() -> None:
    assert assess([_ev(3, "x.com", EvidenceType.SYSTEM_INTERPRETATION)]).label == Confidence.INFERENCE


def test_identity_claims_capped_until_analyst_accepts() -> None:
    evs = [_ev(1, "a.com"), _ev(2, "b.com")]
    assert assess(evs, identity_claim=True).label == Confidence.POSSIBLE
    assert assess(evs, identity_claim=True, review_state=ReviewState.ACCEPTED).label == Confidence.CONFIRMED


def test_rejected_review_contradicts() -> None:
    assert assess([_ev(1, "a.com")], review_state=ReviewState.REJECTED).label == Confidence.CONTRADICTED
