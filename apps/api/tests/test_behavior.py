from decimal import Decimal

from app.calculations.behavior import behavior_score


def test_behavior_score_basic():
    result = behavior_score([Decimal("2"), Decimal("3")])
    assert result.score == Decimal("35")
    assert result.deductions_exceed_base is False


def test_behavior_score_capped_at_zero():
    result = behavior_score([Decimal("20"), Decimal("25")])
    assert result.score == Decimal("0")
    assert result.deductions_exceed_base is True
    assert result.total_approved_deductions == Decimal("45")