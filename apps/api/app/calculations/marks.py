"""Authoritative weighted mark calculations.

Defaults are school-configurable product defaults — not national regulations.
See docs/grading-assumptions.md.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Iterable

from pydantic import BaseModel, Field


class ScoreStatus(str, Enum):
    SCORED = "scored"
    MISSING = "missing"
    ABSENT = "absent"
    EXEMPT = "exempt"
    PENDING = "pending"


class AssessmentScoreInput(BaseModel):
    status: ScoreStatus
    score: Decimal | None = None
    maximum_marks: Decimal = Field(gt=0)


class CategoryInput(BaseModel):
    """One assessment category with weight expressed as a fraction of 1 (e.g. 0.30)."""

    name: str
    weight: Decimal = Field(ge=0)
    scores: list[AssessmentScoreInput]
    exclude_absent_from_denominator: bool = True
    exclude_exempt_from_denominator: bool = True


class CategoryResult(BaseModel):
    name: str
    percentage: Decimal | None
    complete: bool
    applicable_maximum_sum: Decimal
    valid_score_sum: Decimal


class OverallResult(BaseModel):
    overall_percentage: Decimal | None
    provisional: bool
    categories: list[CategoryResult]
    weights_sum: Decimal


def _q(value: Decimal, places: int = 6) -> Decimal:
    quant = Decimal("1").scaleb(-places)
    return value.quantize(quant, rounding=ROUND_HALF_UP)


def compute_category_percentage(category: CategoryInput) -> CategoryResult:
    valid_sum = Decimal("0")
    max_sum = Decimal("0")
    complete = True

    for item in category.scores:
        if item.status == ScoreStatus.MISSING or item.status == ScoreStatus.PENDING:
            complete = False
            continue

        if item.status == ScoreStatus.EXEMPT:
            if not category.exclude_exempt_from_denominator:
                max_sum += item.maximum_marks
            continue

        if item.status == ScoreStatus.ABSENT:
            if not category.exclude_absent_from_denominator:
                max_sum += item.maximum_marks
            continue

        # scored
        if item.score is None:
            complete = False
            continue
        if item.score < 0 or item.score > item.maximum_marks:
            raise ValueError(
                f"Score {item.score} out of range for maximum {item.maximum_marks}"
            )
        valid_sum += item.score
        max_sum += item.maximum_marks

    if max_sum == 0:
        return CategoryResult(
            name=category.name,
            percentage=None,
            complete=complete and len(category.scores) > 0,
            applicable_maximum_sum=max_sum,
            valid_score_sum=valid_sum,
        )

    percentage = _q((valid_sum / max_sum) * Decimal("100"))
    return CategoryResult(
        name=category.name,
        percentage=percentage,
        complete=complete,
        applicable_maximum_sum=max_sum,
        valid_score_sum=valid_sum,
    )


def compute_overall_percentage(
    categories: Iterable[CategoryInput],
    *,
    require_weights_sum_100: bool = True,
    normalize_weights: bool = False,
    allow_incomplete: bool = False,
    display_places: int = 2,
) -> OverallResult:
    cats = list(categories)
    weights_sum = sum((c.weight for c in cats), Decimal("0"))

    if normalize_weights and weights_sum > 0:
        scaled = [
            c.model_copy(update={"weight": c.weight / weights_sum}) for c in cats
        ]
        cats = scaled
        weights_sum = Decimal("1")
    elif require_weights_sum_100:
        # Weights are fractions of 1; 1.00 == 100%
        if _q(weights_sum, 4) != Decimal("1.0000"):
            raise ValueError(
                f"Category weights must sum to 1.0 (100%), got {weights_sum}"
            )

    results: list[CategoryResult] = [compute_category_percentage(c) for c in cats]
    provisional = any(not r.complete or r.percentage is None for r in results)

    if provisional and not allow_incomplete:
        return OverallResult(
            overall_percentage=None,
            provisional=True,
            categories=results,
            weights_sum=weights_sum,
        )

    overall = Decimal("0")
    for cat, result in zip(cats, results, strict=True):
        if result.percentage is None:
            continue
        overall += result.percentage * cat.weight

    return OverallResult(
        overall_percentage=_q(overall, display_places),
        provisional=provisional,
        categories=results,
        weights_sum=weights_sum,
    )