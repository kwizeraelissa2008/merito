"""Pydantic schemas for Phase 3: students, enrollments, assessments, mark entry."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

StudentStatus = Literal["active", "transferred", "withdrawn", "graduated", "deceased"]
ScoreStatus = Literal["scored", "missing", "absent", "exempt", "pending"]
EnrollmentStatus = Literal["active", "transferred", "withdrawn", "completed"]


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------
class StudentCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    student_code: str | None = Field(default=None, max_length=40)
    gender: str | None = None
    date_of_birth: date | None = None
    profile_fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("gender")
    @classmethod
    def valid_gender(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.lower()
        if v not in {"male", "female", "other"}:
            raise ValueError("gender must be male, female, or other")
        return v


class StudentUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    gender: str | None = None
    date_of_birth: date | None = None
    status: StudentStatus | None = None
    profile_fields: dict[str, Any] | None = None


class BulkStudentCreate(BaseModel):
    class_id: uuid.UUID
    academic_year_id: uuid.UUID
    start_date: date
    students: list[StudentCreate] = Field(min_length=1, max_length=1000)


class EnrollmentCreate(BaseModel):
    student_id: uuid.UUID
    class_id: uuid.UUID
    academic_year_id: uuid.UUID
    start_date: date
    end_date: date | None = None

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date | None, info) -> date | None:
        start = info.data.get("start_date")
        if v is not None and start is not None and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v


class StudentTransfer(BaseModel):
    """Close the current enrollment and open a new one in another class."""

    new_class_id: uuid.UUID
    effective_date: date
    reason: str = ""


class StudentWithdrawal(BaseModel):
    withdrawal_date: date
    reason: str = ""
    status: Literal["withdrawn", "transferred", "graduated"] = "withdrawn"


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------
class AssessmentCreate(BaseModel):
    reporting_period_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    category: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=120)
    maximum_marks: Decimal = Field(gt=0, le=1000)
    weight: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    due_date: date | None = None


class AssessmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    maximum_marks: Decimal | None = Field(default=None, gt=0, le=1000)
    weight: Decimal | None = Field(default=None, ge=0, le=1)
    due_date: date | None = None
    status: Literal["draft", "open", "submitted", "locked"] | None = None


# ---------------------------------------------------------------------------
# Mark entry (autosave + bulk submit)
# ---------------------------------------------------------------------------
class ScoreUpsert(BaseModel):
    """A single autosaved cell. `version` enables optimistic concurrency."""

    assessment_id: uuid.UUID
    student_id: uuid.UUID
    status: ScoreStatus = "scored"
    score: Decimal | None = Field(default=None, ge=0)
    version: int | None = Field(
        default=None,
        description="Expected current version for OCC; omit to create.",
    )

    @field_validator("score")
    @classmethod
    def scored_requires_value(cls, v: Decimal | None, info) -> Decimal | None:
        status = info.data.get("status", "scored")
        if status == "scored" and v is None:
            raise ValueError("score is required when status is 'scored'")
        return v


class BulkScoreUpsert(BaseModel):
    """Bulk grid save. Applied atomically; any OCC conflict rejects the batch."""

    scores: list[ScoreUpsert] = Field(min_length=1, max_length=2000)
    idempotency_key: str | None = Field(default=None, max_length=120)


class MarkSheetSubmit(BaseModel):
    reporting_period_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    comment: str = ""


class MarkSheetReview(BaseModel):
    decision: Literal["approved", "returned"]
    note: str = ""


class ScoreConflict(BaseModel):
    assessment_id: uuid.UUID
    student_id: uuid.UUID
    expected_version: int
    current_version: int
    current_score: Decimal | None
    current_status: ScoreStatus


class BulkScoreResult(BaseModel):
    applied: int
    conflicts: list[ScoreConflict] = Field(default_factory=list)
