"""Phase 3 schema validation and OCC/conflict logic tests (no live DB needed)."""

import uuid
from decimal import Decimal

import pytest

from app.api.schemas.students import (
    AssessmentCreate,
    BulkScoreUpsert,
    ScoreUpsert,
    StudentCreate,
    StudentTransfer,
)


def test_student_create_rejects_bad_gender():
    with pytest.raises(ValueError):
        StudentCreate(full_name="Alex Uwase", gender="unknown")


def test_student_create_normalises_gender():
    student = StudentCreate(full_name="Alex Uwase", gender="FEMALE")
    assert student.gender == "female"


def test_score_requires_value_when_scored():
    with pytest.raises(ValueError):
        ScoreUpsert(
            assessment_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            status="scored",
            score=None,
        )


def test_absent_score_can_have_no_value():
    score = ScoreUpsert(
        assessment_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        status="absent",
        score=None,
    )
    assert score.score is None
    assert score.status == "absent"


def test_score_rejects_negative():
    with pytest.raises(ValueError):
        ScoreUpsert(
            assessment_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            status="scored",
            score=Decimal("-1"),
        )


def test_assessment_maximum_bounds():
    with pytest.raises(ValueError):
        AssessmentCreate(
            reporting_period_id=uuid.uuid4(),
            class_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            category="Test",
            title="Test 1",
            maximum_marks=Decimal("0"),  # must be > 0
        )


def test_weight_must_be_fraction():
    with pytest.raises(ValueError):
        AssessmentCreate(
            reporting_period_id=uuid.uuid4(),
            class_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            category="Test",
            title="Test 1",
            maximum_marks=Decimal("20"),
            weight=Decimal("1.5"),  # > 1
        )


def test_bulk_upsert_requires_scores():
    with pytest.raises(ValueError):
        BulkScoreUpsert(scores=[])


def test_transfer_requires_new_class():
    with pytest.raises(ValueError):
        StudentTransfer(new_class_id="not-a-uuid", effective_date="2026-01-01")
