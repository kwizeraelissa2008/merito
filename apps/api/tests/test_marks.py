from decimal import Decimal

from app.calculations.marks import (
    AssessmentScoreInput,
    CategoryInput,
    ScoreStatus,
    compute_overall_percentage,
)


def test_weighted_marks_happy_path():
    categories = [
        CategoryInput(
            name="Tests",
            weight=Decimal("0.4"),
            scores=[
                AssessmentScoreInput(
                    status=ScoreStatus.SCORED, score=Decimal("16"), maximum_marks=Decimal("20")
                ),
                AssessmentScoreInput(
                    status=ScoreStatus.SCORED, score=Decimal("18"), maximum_marks=Decimal("20")
                ),
            ],
        ),
        CategoryInput(
            name="Exam",
            weight=Decimal("0.6"),
            scores=[
                AssessmentScoreInput(
                    status=ScoreStatus.SCORED, score=Decimal("70"), maximum_marks=Decimal("100")
                ),
            ],
        ),
    ]
    result = compute_overall_percentage(categories)
    assert result.provisional is False
    assert result.overall_percentage == Decimal("76.00")


def test_missing_mark_is_provisional_and_not_zero():
    categories = [
        CategoryInput(
            name="Exam",
            weight=Decimal("1.0"),
            scores=[
                AssessmentScoreInput(status=ScoreStatus.MISSING, maximum_marks=Decimal("100")),
            ],
        )
    ]
    result = compute_overall_percentage(categories)
    assert result.provisional is True
    assert result.overall_percentage is None


def test_exempt_excluded_from_denominator():
    categories = [
        CategoryInput(
            name="Quiz",
            weight=Decimal("1.0"),
            scores=[
                AssessmentScoreInput(
                    status=ScoreStatus.SCORED, score=Decimal("8"), maximum_marks=Decimal("10")
                ),
                AssessmentScoreInput(status=ScoreStatus.EXEMPT, maximum_marks=Decimal("10")),
            ],
        )
    ]
    result = compute_overall_percentage(categories)
    assert result.categories[0].percentage == Decimal("80.000000")
    assert result.overall_percentage == Decimal("80.00")


def test_zero_is_distinct_from_missing():
    categories = [
        CategoryInput(
            name="Quiz",
            weight=Decimal("1.0"),
            scores=[
                AssessmentScoreInput(
                    status=ScoreStatus.SCORED, score=Decimal("0"), maximum_marks=Decimal("10")
                ),
            ],
        )
    ]
    result = compute_overall_percentage(categories)
    assert result.provisional is False
    assert result.overall_percentage == Decimal("0.00")