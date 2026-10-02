"""Investigation state machine. Transitions are validated here and nowhere else."""

from __future__ import annotations

from eyohe.core.enums import InvestigationStatus as S
from eyohe.core.errors import InvalidTransitionError

TRANSITIONS: dict[S, set[S]] = {
    S.DRAFT: {S.PLANNING},
    S.PLANNING: {S.AWAITING_APPROVAL, S.FAILED, S.DRAFT},
    S.AWAITING_APPROVAL: {S.RUNNING, S.DRAFT, S.PLANNING},
    S.RUNNING: {S.PAUSED, S.VERIFYING, S.STOPPED, S.FAILED, S.COMPLETED},
    S.PAUSED: {S.RUNNING, S.STOPPED},
    S.VERIFYING: {S.COMPLETED, S.FAILED, S.STOPPED, S.RUNNING},
    S.COMPLETED: {S.RUNNING},  # re-run / expand research
    S.STOPPED: {S.RUNNING, S.DRAFT},
    S.FAILED: {S.RUNNING, S.DRAFT, S.PLANNING},
}

TERMINAL = {S.COMPLETED, S.STOPPED, S.FAILED}
ACTIVE = {S.PLANNING, S.RUNNING, S.VERIFYING}


def assert_transition(current: str, new: str) -> None:
    cur, nxt = S(current), S(new)
    if nxt not in TRANSITIONS.get(cur, set()):
        raise InvalidTransitionError(
            f"Cannot move investigation from {cur} to {nxt}.",
            detail={"from": cur, "to": nxt, "allowed": sorted(TRANSITIONS.get(cur, set()))},
        )
