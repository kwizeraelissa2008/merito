"""Behavioral score = base − approved deductions (capped at zero)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class BehaviorResult(BaseModel):
    base: Decimal
    total_approved_deductions: Decimal
    score: Decimal
    deductions_exceed_base: bool


def behavior_score(
    approved_deductions: list[Decimal],
    *,
    base: Decimal = Decimal("40"),
) -> BehaviorResult:
    if base < 0:
        raise ValueError("Behavior base must be >= 0")
    total = sum(approved_deductions, Decimal("0"))
    if any(d <= 0 for d in approved_deductions):
        raise ValueError("Deductions must be positive")
    exceed = total > base
    score = base - total
    if score < 0:
        score = Decimal("0")
    return BehaviorResult(
        base=base,
        total_approved_deductions=total,
        score=score,
        deductions_exceed_base=exceed,
    )


class IncidentDeduction(BaseModel):
    amount: Decimal = Field(gt=0)