"""Tests for Phase 2 configuration validation and authorization helpers.

These exercise pure logic and the router-level validation that does not require a
live database. Database/RLS behaviour is covered by the SQL policy tests and the
end-to-end phase tests run against a local Supabase instance.
"""

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.schemas.configuration import (
    AcademicYearCreate,
    GradingBandCreate,
    InvitationCreate,
    SubjectCreate,
    TeachingAssignmentCreate,
)
from app.core.auth import parse_school_id
from app.services.imports import weights_sum_to_one


def test_subject_code_is_normalised_to_uppercase():
    subject = SubjectCreate(name="Mathematics", code="math", category="core")
    assert subject.code == "MATH"


def test_academic_year_end_must_follow_start():
    with pytest.raises(ValueError):
        AcademicYearCreate(
            name="2025-2026",
            start_date="2026-01-01",  # type: ignore[arg-type]
            end_date="2025-01-01",  # type: ignore[arg-type]
        )


def test_grading_band_percentage_bounds():
    with pytest.raises(ValueError):
        GradingBandCreate(
            grading_policy_id=uuid.uuid4(),
            letter="A",
            min_percentage=Decimal("120"),
        )


def test_invitation_requires_valid_email():
    with pytest.raises(ValueError):
        InvitationCreate(email="not-an-email", role="subject_teacher")  # type: ignore[arg-type]


def test_invitation_scope_defaults_empty():
    invitation = InvitationCreate(email="teacher@example.com", role="subject_teacher")
    assert invitation.scope == {}
    assert invitation.expires_in_days == 14


def test_parse_school_id_rejects_garbage():
    with pytest.raises(HTTPException) as exc:
        parse_school_id("not-a-uuid")
    assert exc.value.status_code == 400


def test_parse_school_id_accepts_uuid():
    value = str(uuid.uuid4())
    assert str(parse_school_id(value)) == value


def test_teaching_assignment_requires_uuids():
    with pytest.raises(ValueError):
        TeachingAssignmentCreate(
            teacher_user_id="bad",  # type: ignore[arg-type]
            class_id=str(uuid.uuid4()),
            subject_id=str(uuid.uuid4()),
            academic_year_id=str(uuid.uuid4()),
        )


def test_default_category_weights_sum_to_one():
    # The seed category set (10% + 10% + 30% + 10% + 40%) must validate.
    weights = [Decimal("0.10"), Decimal("0.10"), Decimal("0.30"),
               Decimal("0.10"), Decimal("0.40")]
    assert weights_sum_to_one(weights)
