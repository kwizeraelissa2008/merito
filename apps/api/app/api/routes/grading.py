"""Phase 2 grading configuration: policies, bands, assessment categories."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.configuration import (
    AssessmentCategoryCreate,
    GradingBandCreate,
    GradingPolicyCreate,
)
from app.core.auth import CurrentUserDep, client_for, parse_school_id, require_school_role
from app.services.imports import weights_sum_to_one

router = APIRouter(prefix="/schools", tags=["grading"])

ADMIN = ("school_admin",)
READ_ROLES = ("school_admin", "principal", "dean_of_discipline", "hod_moderator",
              "subject_teacher", "class_teacher")


@router.get("/{school_id}/grading-policies", response_model=list)
async def list_grading_policies(school_id: str, user: CurrentUserDep) -> list[dict[str, Any]]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, READ_ROLES)
    return await client_for(user).select(
        "grading_policies",
        params={"school_id": f"eq.{sid}", "select": "*", "order": "version.desc"},
    )


@router.post(
    "/{school_id}/grading-policies",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_grading_policy(
    school_id: str, body: GradingPolicyCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "grading_policies",
        {"school_id": str(sid), **body.model_dump(mode="json")},
    )
    await client_for(user).insert(
        "audit_logs",
        {
            "school_id": str(sid),
            "actor_id": str(user.id),
            "action": "grading_policy.created",
            "entity_type": "grading_policies",
            "entity_id": rows[0]["id"],
            "new_value": body.model_dump(mode="json"),
        },
    )
    return rows[0]


# ---------------------------------------------------------------------------
# Assessment categories
# ---------------------------------------------------------------------------
@router.get("/{school_id}/assessment-categories", response_model=list)
async def list_assessment_categories(
    school_id: str, user: CurrentUserDep
) -> list[dict[str, Any]]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, READ_ROLES)
    return await client_for(user).select(
        "assessment_categories",
        params={"school_id": f"eq.{sid}", "select": "*", "order": "ordering.asc"},
    )


@router.post(
    "/{school_id}/assessment-categories",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_assessment_category(
    school_id: str, body: AssessmentCategoryCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "assessment_categories",
        {"school_id": str(sid), **body.model_dump(mode="json")},
    )
    return rows[0]


@router.post("/{school_id}/assessment-categories/validate-weights", response_model=dict)
async def validate_weights(school_id: str, user: CurrentUserDep) -> dict[str, Any]:
    """Check whether the active category weights sum to 100% (1.0)."""
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, READ_ROLES)
    from decimal import Decimal

    rows = await client_for(user).select(
        "assessment_categories",
        params={"school_id": f"eq.{sid}", "select": "code,default_weight,active",
                "active": "eq.true"},
    )
    weights = [Decimal(str(r["default_weight"])) for r in rows]
    total = sum(weights, Decimal("0"))
    return {
        "category_count": len(rows),
        "weights_sum": str(total),
        "valid": weights_sum_to_one(weights) if rows else False,
    }


# ---------------------------------------------------------------------------
# Grading bands
# ---------------------------------------------------------------------------
@router.get("/{school_id}/grading-policies/{policy_id}/bands", response_model=list)
async def list_grading_bands(
    school_id: str, policy_id: str, user: CurrentUserDep
) -> list[dict[str, Any]]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, READ_ROLES)
    return await client_for(user).select(
        "grading_bands",
        params={
            "school_id": f"eq.{sid}",
            "grading_policy_id": f"eq.{policy_id}",
            "select": "*",
            "order": "min_percentage.desc",
        },
    )


@router.post(
    "/{school_id}/grading-bands",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_grading_band(
    school_id: str, body: GradingBandCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "grading_bands",
        {"school_id": str(sid), **body.model_dump(mode="json")},
    )
    return rows[0]


@router.post("/{school_id}/grading-bands/validate", response_model=dict)
async def validate_grading_bands(
    school_id: str, body: dict[str, str], user: CurrentUserDep
) -> dict[str, Any]:
    """Validate a band set before saving: unique letters and lowest min == 0."""
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    bands = body.get("bands", [])
    if not isinstance(bands, list) or not bands:
        raise HTTPException(status_code=400, detail="bands must be a non-empty list")
    errors: list[str] = []
    letters = [str(b.get("letter", "")).strip().upper() for b in bands]
    if len(letters) != len(set(letters)):
        errors.append("Band letters must be unique")
    try:
        mins = sorted(float(b.get("min_percentage", 0)) for b in bands)
    except (TypeError, ValueError):
        errors.append("min_percentage values must be numeric")
        mins = []
    if mins and abs(mins[0]) > 1e-9:
        errors.append("The lowest band must start at 0%")
    return {"valid": not errors, "errors": errors}
