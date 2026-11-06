"""Pydantic schemas for Phase 2 school-configuration endpoints.

All payloads are tenant-scoped: the school is taken from the URL path, never the
body, so a malicious body cannot target another tenant.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

MembershipRole = Literal[
    "school_admin",
    "principal",
    "dean_of_discipline",
    "discipline_staff",
    "subject_teacher",
    "class_teacher",
    "hod_moderator",
    "student",
    "guardian",
]

AcademicLevel = Literal["olevel", "alevel", "legacy_s6", "custom"]
SubjectCategory = Literal["core", "minor", "optional", "other"]


# ---------------------------------------------------------------------------
# School identity
# ---------------------------------------------------------------------------
class SchoolContactDetails(BaseModel):
    address: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    motto: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class SchoolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    contact_details: SchoolContactDetails | None = None
    logo_path: str | None = None
    timezone: str | None = None


# ---------------------------------------------------------------------------
# Academic calendar
# ---------------------------------------------------------------------------
class AcademicYearCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v <= start:
            raise ValueError("end_date must be after start_date")
        return v


class TermCreate(BaseModel):
    academic_year_id: uuid.UUID
    term_number: int = Field(ge=1, le=6)
    name: str = Field(min_length=1, max_length=60)
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v <= start:
            raise ValueError("end_date must be after start_date")
        return v


class ReportingPeriodCreate(BaseModel):
    term_id: uuid.UUID
    period_number: int = Field(ge=1, le=12)
    name: str = Field(min_length=1, max_length=60)
    start_date: date
    end_date: date
    deadlines: dict[str, str] = Field(default_factory=dict)

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v


# ---------------------------------------------------------------------------
# Curriculum structure
# ---------------------------------------------------------------------------
class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=20)
    category: SubjectCategory = "core"

    @field_validator("code")
    @classmethod
    def normalise_code(cls, v: str) -> str:
        return v.strip().upper()


class CurriculumCreate(BaseModel):
    academic_year_id: uuid.UUID | None = None
    name: str = Field(min_length=2, max_length=120)
    level: AcademicLevel
    effective_from: date | None = None
    effective_to: date | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)


class GradeCreate(BaseModel):
    curriculum_id: uuid.UUID
    name: str = Field(min_length=1, max_length=40)
    level: AcademicLevel
    ordering: int = 0


class CombinationCreate(BaseModel):
    curriculum_id: uuid.UUID
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    description: str = ""

    @field_validator("code")
    @classmethod
    def normalise_code(cls, v: str) -> str:
        return v.strip().upper()


class CurriculumSubjectCreate(BaseModel):
    curriculum_id: uuid.UUID
    subject_id: uuid.UUID
    grade_id: uuid.UUID | None = None
    combination_id: uuid.UUID | None = None
    maximum_marks: Decimal | None = Field(default=None, gt=0)
    ordering: int = 0
    configuration: dict[str, Any] = Field(default_factory=dict)


class ClassCreate(BaseModel):
    academic_year_id: uuid.UUID
    grade_id: uuid.UUID
    combination_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=60)


class ClassStreamBulkCreate(BaseModel):
    """Create several streams for one grade in a single transactional request."""

    academic_year_id: uuid.UUID
    grade_id: uuid.UUID
    combination_id: uuid.UUID | None = None
    base_name: str = Field(min_length=1, max_length=40)
    stream_labels: list[str] = Field(min_length=1, max_length=26)


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------
class TeachingAssignmentCreate(BaseModel):
    teacher_user_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    academic_year_id: uuid.UUID
    starts_on: date | None = None
    ends_on: date | None = None


class ClassTeacherAssignmentCreate(BaseModel):
    teacher_user_id: uuid.UUID
    class_id: uuid.UUID
    academic_year_id: uuid.UUID
    starts_on: date | None = None
    ends_on: date | None = None


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------
class InvitationCreate(BaseModel):
    email: EmailStr
    full_name: str = ""
    role: MembershipRole
    expires_in_days: int = Field(default=14, ge=1, le=60)
    scope: dict[str, Any] = Field(default_factory=dict)


class InvitationAccept(BaseModel):
    token: str = Field(min_length=10)


# ---------------------------------------------------------------------------
# Grading configuration
# ---------------------------------------------------------------------------
class AssessmentCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    code: str = Field(min_length=1, max_length=20)
    default_maximum_marks: Decimal = Field(gt=0)
    default_weight: Decimal = Field(ge=0, le=1)
    exclude_absent_from_denominator: bool = True
    exclude_exempt_from_denominator: bool = True
    is_optional: bool = False
    ordering: int = 0

    @field_validator("code")
    @classmethod
    def normalise_code(cls, v: str) -> str:
        return v.strip().upper()


class GradingBandCreate(BaseModel):
    grading_policy_id: uuid.UUID
    letter: str = Field(min_length=1, max_length=4)
    descriptor: str = ""
    min_percentage: Decimal = Field(ge=0, le=100)
    is_pass: bool = True
    comment_hint: str = ""
    ordering: int = 0


class GradingPolicyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    version: int = Field(default=1, ge=1)
    effective_from: date | None = None
    effective_to: date | None = None
    policy_configuration: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Configuration CSV import
# ---------------------------------------------------------------------------
class ImportPreviewRow(BaseModel):
    row_number: int
    status: Literal["ok", "warning", "error"]
    messages: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class ImportPreviewResponse(BaseModel):
    entity: str
    total_rows: int
    ok_rows: int
    warning_rows: int
    error_rows: int
    rows: list[ImportPreviewRow]


class ImportCommitRequest(BaseModel):
    entity: Literal["subjects", "classes", "students"]
    rows: list[dict[str, Any]] = Field(min_length=1)


class ImportCommitResponse(BaseModel):
    entity: str
    inserted: int
    skipped: int


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------
class OnboardingState(BaseModel):
    school_id: uuid.UUID
    current_step: str
    steps: dict[str, Any]
    completed_at: datetime | None
    updated_at: datetime | None
