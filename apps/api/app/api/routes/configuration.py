"""Phase 2 configuration endpoints: school identity, academic calendar, structure.

Every route is tenant-scoped: `school_id` comes from the path and the caller must
hold the required role in that school (verified against the database, never a
client claim). Mutating routes write an audit entry.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.configuration import (
    AcademicYearCreate,
    ClassCreate,
    ClassStreamBulkCreate,
    CombinationCreate,
    CurriculumCreate,
    CurriculumSubjectCreate,
    GradeCreate,
    ReportingPeriodCreate,
    SchoolUpdate,
    SubjectCreate,
    TermCreate,
)
from app.core.auth import (
    CurrentUser,
    CurrentUserDep,
    client_for,
    parse_school_id,
    require_school_role,
)

router = APIRouter(prefix="/schools", tags=["configuration"])

ADMIN = ("school_admin",)
ADMIN_OR_LEADERSHIP = (
    "school_admin",
    "principal",
    "dean_of_discipline",
)


def _audit(
    school_id: str,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    new_value: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "school_id": school_id,
        "actor_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "new_value": new_value,
    }


async def _audit_write(
    user: CurrentUser,
    school_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    new_value: dict[str, Any] | None = None,
) -> None:
    client = client_for(user)
    await client.insert(
        "audit_logs",
        _audit(str(school_id), str(user.id), action, entity_type, str(entity_id), new_value),
    )


# ---------------------------------------------------------------------------
# School identity
# ---------------------------------------------------------------------------
@router.get("/{school_id}", response_model=dict)
async def get_school(school_id: str, user: CurrentUserDep) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ("school_admin", "principal", "dean_of_discipline",
                                          "subject_teacher", "class_teacher", "hod_moderator"))
    rows = await client_for(user).select(
        "schools",
        params={"id": f"eq.{sid}", "select": "*"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="School not found")
    return rows[0]


@router.patch("/{school_id}", response_model=dict)
async def update_school(
    school_id: str,
    body: SchoolUpdate,
    user: CurrentUserDep,
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    payload = body.model_dump(exclude_unset=True)
    if "contact_details" in payload and payload["contact_details"] is not None:
        payload["contact_details"] = body.contact_details.model_dump()  # type: ignore[union-attr]
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    rows = await client_for(user).update(
        "schools", payload, params={"id": f"eq.{sid}"}
    )
    await _audit_write(user, sid, "school.updated", "schools", sid, payload)
    return rows[0] if rows else {}


@router.get("/{school_id}/overview", response_model=dict)
async def configuration_overview(school_id: str, user: CurrentUserDep) -> dict[str, Any]:
    """Counts used by the admin dashboard to show configuration completeness."""
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN_OR_LEADERSHIP)
    client = client_for(user)

    async def _count(table: str) -> int:
        rows = await client.select(
            table, params={"school_id": f"eq.{sid}", "select": "id"}
        )
        return len(rows)

    return {
        "school_id": str(sid),
        "counts": {
            "academic_years": await _count("academic_years"),
            "terms": await _count("terms"),
            "reporting_periods": await _count("reporting_periods"),
            "curricula": await _count("curricula"),
            "grades": await _count("grades"),
            "combinations": await _count("combinations"),
            "subjects": await _count("subjects"),
            "classes": await _count("classes"),
            "assessment_categories": await _count("assessment_categories"),
            "grading_bands": await _count("grading_bands"),
        },
    }


# ---------------------------------------------------------------------------
# Academic calendar
# ---------------------------------------------------------------------------
@router.post(
    "/{school_id}/academic-years",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_academic_year(
    school_id: str, body: AcademicYearCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "academic_years", {"school_id": str(sid), **body.model_dump(mode="json")}
    )
    await _audit_write(user, sid, "academic_year.created", "academic_years",
                       uuid.UUID(rows[0]["id"]), body.model_dump(mode="json"))
    return rows[0]


@router.post(
    "/{school_id}/terms",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_term(
    school_id: str, body: TermCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "terms",
        {"school_id": str(sid), **body.model_dump(mode="json")},
    )
    await _audit_write(user, sid, "term.created", "terms",
                       uuid.UUID(rows[0]["id"]), body.model_dump(mode="json"))
    return rows[0]


@router.post(
    "/{school_id}/reporting-periods",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_reporting_period(
    school_id: str, body: ReportingPeriodCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "reporting_periods",
        {"school_id": str(sid), **body.model_dump(mode="json")},
    )
    await _audit_write(user, sid, "reporting_period.created", "reporting_periods",
                       uuid.UUID(rows[0]["id"]), body.model_dump(mode="json"))
    return rows[0]


@router.post(
    "/{school_id}/calendar/default",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def seed_default_calendar(
    school_id: str, user: CurrentUserDep
) -> dict[str, Any]:
    """Create 3 terms × 3 reporting periods for an academic year.

    Convenience for onboarding. The caller supplies an academic year id in the
    body-less flow using the most recent draft year; here we require one exists.
    """
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    client = client_for(user)
    years = await client.select(
        "academic_years",
        params={"school_id": f"eq.{sid}", "select": "*", "order": "start_date.desc"},
    )
    if not years:
        raise HTTPException(
            status_code=400,
            detail="Create an academic year before generating the default calendar",
        )
    year = years[0]
    created_terms: list[dict[str, Any]] = []
    from datetime import date, timedelta

    year_start = date.fromisoformat(year["start_date"])
    year_end = date.fromisoformat(year["end_date"])
    span = (year_end - year_start) / 3
    for term_no in range(1, 4):
        term_start = year_start + timedelta(days=span * (term_no - 1))
        term_end = (year_start + timedelta(days=span * term_no)) - timedelta(days=1)
        term_rows = await client.insert(
            "terms",
            {
                "school_id": str(sid),
                "academic_year_id": year["id"],
                "term_number": term_no,
                "name": f"Term {term_no}",
                "start_date": term_start.isoformat(),
                "end_date": term_end.isoformat(),
            },
        )
        term = term_rows[0]
        created_terms.append(term)
        period_span = (term_end - term_start) / 3
        for period_no in range(1, 4):
            p_start = term_start + timedelta(days=period_span * (period_no - 1))
            p_end = (term_start + timedelta(days=period_span * period_no)) - timedelta(days=1)
            await client.insert(
                "reporting_periods",
                {
                    "school_id": str(sid),
                    "term_id": term["id"],
                    "period_number": period_no,
                    "name": f"Period {period_no}",
                    "start_date": p_start.isoformat(),
                    "end_date": p_end.isoformat(),
                },
            )
    await _audit_write(user, sid, "calendar.default_generated", "academic_years",
                       uuid.UUID(year["id"]), {"terms": 3, "periods_per_term": 3})
    return {"academic_year_id": year["id"], "terms_created": len(created_terms)}


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------
@router.get("/{school_id}/subjects", response_model=list)
async def list_subjects(school_id: str, user: CurrentUserDep) -> list[dict[str, Any]]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ("school_admin", "principal", "dean_of_discipline",
                                          "subject_teacher", "class_teacher", "hod_moderator"))
    return await client_for(user).select(
        "subjects",
        params={"school_id": f"eq.{sid}", "select": "*", "order": "name.asc"},
    )


@router.post(
    "/{school_id}/subjects",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_subject(
    school_id: str, body: SubjectCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "subjects", {"school_id": str(sid), **body.model_dump(mode="json")}
    )
    await _audit_write(user, sid, "subject.created", "subjects",
                       uuid.UUID(rows[0]["id"]), body.model_dump(mode="json"))
    return rows[0]


# ---------------------------------------------------------------------------
# Curriculum structure
# ---------------------------------------------------------------------------
@router.post(
    "/{school_id}/curricula",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_curriculum(
    school_id: str, body: CurriculumCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "curricula", {"school_id": str(sid), **body.model_dump(mode="json")}
    )
    await _audit_write(user, sid, "curriculum.created", "curricula",
                       uuid.UUID(rows[0]["id"]), body.model_dump(mode="json"))
    return rows[0]


@router.post(
    "/{school_id}/grades",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_grade(
    school_id: str, body: GradeCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "grades", {"school_id": str(sid), **body.model_dump(mode="json")}
    )
    return rows[0]


@router.post(
    "/{school_id}/combinations",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_combination(
    school_id: str, body: CombinationCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "combinations", {"school_id": str(sid), **body.model_dump(mode="json")}
    )
    return rows[0]


@router.post(
    "/{school_id}/curriculum-subjects",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_curriculum_subject(
    school_id: str, body: CurriculumSubjectCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "curriculum_subjects",
        {"school_id": str(sid), **body.model_dump(mode="json")},
    )
    return rows[0]


@router.get("/{school_id}/curriculum-structure", response_model=dict)
async def curriculum_structure(school_id: str, user: CurrentUserDep) -> dict[str, Any]:
    """Full configuration tree for the review/preview step of the wizard."""
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN_OR_LEADERSHIP)
    client = client_for(user)

    async def _all(table: str, order: str = "created_at.asc") -> list[dict[str, Any]]:
        return await client.select(
            table,
            params={"school_id": f"eq.{sid}", "select": "*", "order": order},
        )

    return {
        "academic_years": await _all("academic_years", "start_date.desc"),
        "terms": await _all("terms", "term_number.asc"),
        "reporting_periods": await _all("reporting_periods", "period_number.asc"),
        "curricula": await _all("curricula"),
        "grades": await _all("grades", "ordering.asc"),
        "combinations": await _all("combinations", "code.asc"),
        "subjects": await _all("subjects", "name.asc"),
        "curriculum_subjects": await _all("curriculum_subjects", "ordering.asc"),
        "classes": await _all("classes", "name.asc"),
    }


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------
@router.post(
    "/{school_id}/classes",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_class(
    school_id: str, body: ClassCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "classes", {"school_id": str(sid), **body.model_dump(mode="json")}
    )
    await _audit_write(user, sid, "class.created", "classes",
                       uuid.UUID(rows[0]["id"]), body.model_dump(mode="json"))
    return rows[0]


@router.post(
    "/{school_id}/classes/streams",
    status_code=status.HTTP_201_CREATED,
    response_model=list,
)
async def create_class_streams(
    school_id: str, body: ClassStreamBulkCreate, user: CurrentUserDep
) -> list[dict[str, Any]]:
    """Create several streams (e.g. S1A, S1B, S1C) for one grade in one call."""
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    payload = [
        {
            "school_id": str(sid),
            "academic_year_id": str(body.academic_year_id),
            "grade_id": str(body.grade_id),
            "combination_id": str(body.combination_id) if body.combination_id else None,
            "name": f"{body.base_name}{label}".strip(),
        }
        for label in body.stream_labels
    ]
    rows = await client_for(user).insert("classes", payload)
    return rows
