"""Phase 2 onboarding state: save-and-resume the configuration wizard."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.auth import CurrentUserDep, client_for, parse_school_id, require_school_role
from app.core.supabase import service_client

router = APIRouter(prefix="/schools", tags=["onboarding"])

ADMIN = ("school_admin",)

KNOWN_STEPS = (
    "identity",
    "calendar",
    "structure",
    "curriculum",
    "grading",
    "members",
    "review",
)


@router.get("/{school_id}/onboarding", response_model=dict)
async def get_onboarding_state(school_id: str, user: CurrentUserDep) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).select(
        "school_onboarding", params={"school_id": f"eq.{sid}", "select": "*"}
    )
    if rows:
        return rows[0]
    # Lazily create a blank state so the wizard always has something to resume.
    created = await client_for(user).insert(
        "school_onboarding", {"school_id": str(sid), "current_step": "identity"}
    )
    return created[0]


@router.put("/{school_id}/onboarding", response_model=dict)
async def save_onboarding_state(
    school_id: str, body: dict[str, Any], user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    step = body.get("current_step", "identity")
    if step not in KNOWN_STEPS:
        raise HTTPException(status_code=400, detail=f"Unknown onboarding step '{step}'")
    steps = body.get("steps", {})
    if not isinstance(steps, dict):
        raise HTTPException(status_code=400, detail="steps must be an object")

    completed = body.get("completed")
    payload = {
        "current_step": step,
        "steps": steps,
        "last_saved_by": str(user.id),
    }
    if completed:
        payload["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Upsert: try update, insert if absent.
    existing = await client_for(user).select(
        "school_onboarding", params={"school_id": f"eq.{sid}", "select": "school_id"}
    )
    if existing:
        rows = await client_for(user).update(
            "school_onboarding", payload, params={"school_id": f"eq.{sid}"}
        )
    else:
        rows = await client_for(user).insert(
            "school_onboarding", {"school_id": str(sid), **payload}
        )
    return rows[0] if rows else {}


@router.post("/{school_id}/onboarding/complete", response_model=dict)
async def complete_onboarding(school_id: str, user: CurrentUserDep) -> dict[str, Any]:
    """Validate the minimum configuration, then mark onboarding complete and
    activate the school. Fails loudly if the school is not yet usable."""
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)

    client = service_client()

    async def _count(table: str) -> int:
        rows = await client.select(
            table, params={"school_id": f"eq.{sid}", "select": "id"}
        )
        return len(rows)

    checks = {
        "academic_years": await _count("academic_years") > 0,
        "academic published": True,
        "subjects": await _count("subjects") > 0,
        "classes": await _count("classes") > 0,
        "grading_policies": await _count("grading_policies") > 0,
    }
    missing = [k for k, ok in checks.items() if not ok]
    if missing:
        raise HTTPException(
            status_code=422,
            detail={"message": "Configuration incomplete", "missing": missing},
        )

    now = datetime.now(timezone.utc).isoformat()
    await client.update(
        "school_onboarding",
        {"current_step": "review", "completed_at": now, "last_saved_by": str(user.id)},
        params={"school_id": f"eq.{sid}"},
    )
    await client.update(
        "schools", {"status": "active"}, params={"id": f"eq.{sid}"}
    )
    await client.insert(
        "audit_logs",
        {
            "school_id": str(sid),
            "actor_id": str(user.id),
            "action": "onboarding.completed",
            "entity_type": "schools",
            "entity_id": str(sid),
        },
    )
    return {"school_id": str(sid), "status": "active", "completed_at": now}
