"""Ranking with shared positions for ties — no name/code/DB-order tie-breakers."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel


class RankPolicy(str, Enum):
    """Dense/shared: 1,2,2,4 style (competition ranking)."""

    COMPETITION = "competition"


class RankEntry(BaseModel):
    entity_id: str
    score: Decimal
    eligible: bool = True


class RankResult(BaseModel):
    entity_id: str
    score: Decimal
    position: int | None


def rank_scores(
    entries: list[RankEntry],
    *,
    policy: RankPolicy = RankPolicy.COMPETITION,
    higher_is_better: bool = True,
) -> list[RankResult]:
    if policy != RankPolicy.COMPETITION:
        raise ValueError(f"Unsupported rank policy: {policy}")

    eligible = [e for e in entries if e.eligible]
    ineligible = [e for e in entries if not e.eligible]

    ordered = sorted(
        eligible,
        key=lambda e: e.score,
        reverse=higher_is_better,
    )

    results: list[RankResult] = []
    i = 0
    while i < len(ordered):
        j = i
        while j < len(ordered) and ordered[j].score == ordered[i].score:
            j += 1
        position = i + 1  # competition rank
        for k in range(i, j):
            results.append(
                RankResult(
                    entity_id=ordered[k].entity_id,
                    score=ordered[k].score,
                    position=position,
                )
            )
        i = j

    for e in ineligible:
        results.append(
            RankResult(entity_id=e.entity_id, score=e.score, position=None)
        )

    return results