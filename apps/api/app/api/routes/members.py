"""Phase 2 membership endpoints: invitations, memberships, and assignments.

Security notes:
  * Invitation tokens are generated here and only their SHA-256 hash is stored.
    The raw token is returned once to the inviter for delivery (email/print);
    it is never persisted and never logged.
  * Acceptance is a database RPC (``accept_invitation``) that re-validates the
    token, expiry, status and email match before creating anything.
  * Assignment creation is restricted to school admins.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.configuration import (
    ClassTeacherAssignmentCreate,
    InvitationAccept,
    InvitationCreate,
    TeachingAssignmentCreate,
)
from app.core.auth import (
    CurrentUserDep,
    client_for,
    parse_school_id,
    require_school_role,
)
from app.core.supabase import service_client

router = APIRouter(prefix="/schools", tags=["membership"])

ADMIN = ("school_admin",)


def _generate_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hex). The raw token is shown once and discarded."""
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, digest


# ---------------------------------------------------------------------------
# Memberships
# ---------------------------------------------------------------------------
@router.get("/{school_id}/members", response_model=list)
async def list_members(school_id: str, user: CurrentUserDep) -> list[dict[str, Any]]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ("school_admin", "principal", "dean_of_discipline"))
    rows = await service_client().select(
        "school_memberships",
        params={
            "school_id": f"eq.{sid}",
            "select": "id,user_id,role,status,created_at,profiles(full_name,email)",
            "order": "created_at.desc",
        },
    )
    return rows


@router.post("/{school_id}/members/{membership_id}/status", response_model=dict)
async def set_member_status(
    school_id: str,
    membership_id: str,
    body: dict[str, str],
    user: CurrentUserDep,
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    new_status = body.get("status")
    if new_status not in {"active", "suspended", "deactivated"}:
        raise HTTPException(status_code=400, detail="Invalid membership status")
    rows = await client_for(user).update(
        "school_memberships",
        {"status": new_status},
        params={"id": f"eq.{membership_id}", "school_id": f"eq.{sid}"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Membership not found")
    await client_for(user).insert(
        "audit_logs",
        {
            "school_id": str(sid),
            "actor_id": str(user.id),
            "action": "membership.status_changed",
            "entity_type": "school_memberships",
            "entity_id": membership_id,
            "new_value": {"status": new_status},
        },
    )
    return rows[0]


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------
@router.get("/{school_id}/invitations", response_model=list)
async def list_invitations(school_id: str, user: CurrentUserDep) -> list[dict[str, Any]]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    return await client_for(user).select(
        "user_invitations",
        params={
            "school_id": f"eq.{sid}",
            "select": "id,email,full_name,role,status,expires_at,accepted_at,revoked_at,created_at",
            "order": "created_at.desc",
        },
    )


@router.post(
    "/{school_id}/invitations",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_invitation(
    school_id: str, body: InvitationCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)

    raw_token, token_hash = _generate_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)

    rows = await client_for(user).insert(
        "user_invitations",
        {
            "school_id": str(sid),
            "email": body.email,
            "full_name": body.full_name,
            "role": body.role,
            "token_hash": token_hash,
            "expires_at": expires_at.isoformat(),
            "scope": body.scope,
            "invited_by": str(user.id),
        },
    )
    invitation = rows[0]
    # Raw token returned exactly once for delivery. Not persisted anywhere.
    return {
        "id": invitation["id"],
        "email": invitation["email"],
        "role": invitation["role"],
        "status": invitation["status"],
        "expires_at": invitation["expires_at"],
        "accept_url": f"/invitations/accept?token={raw_token}",
    }


@router.post("/{school_id}/invitations/{invitation_id}/revoke", response_model=dict)
async def revoke_invitation(
    school_id: str, invitation_id: str, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    result = await client_for(user).rpc(
        "revoke_invitation", {"p_invitation_id": invitation_id}
    )
    return result if isinstance(result, dict) else {"revoked": True}


@router.post("/invitations/accept", response_model=dict)
async def accept_invitation(body: InvitationAccept, user: CurrentUserDep) -> dict[str, Any]:
    """Accept an invitation for the currently signed-in user (email must match)."""
    result = await client_for(user).rpc("accept_invitation", {"p_token": body.token})
    return result if isinstance(result, dict) else {"accepted": True}


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------
@router.get("/{school_id}/teaching-assignments", response_model=list)
async def list_teaching_assignments(
    school_id: str, user: CurrentUserDep
) -> list[dict[str, Any]]:
    sid = parse_school_id(school_id)
    await require_school_role(
        user, sid, ("school_admin", "principal", "dean_of_discipline", "hod_moderator")
    )
    return await client_for(user).select(
        "teaching_assignments",
        params={"school_id": f"eq.{sid}", "select": "*", "order": "created_at.desc"},
    )


@router.post(
    "/{school_id}/teaching-assignments",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_teaching_assignment(
    school_id: str, body: TeachingAssignmentCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "teaching_assignments",
        {"school_id": str(sid), **body.model_dump(mode="json")},
    )
    return rows[0]


@router.get("/{school_id}/class-teacher-assignments", response_model=list)
async def list_class_teacher_assignments(
    school_id: str, user: CurrentUserDep
) -> list[dict[str, Any]]:
    sid = parse_school_id(school_id)
    await require_school_role(
        user, sid, ("school_admin", "principal", "dean_of_discipline")
    )
    return await client_for(user).select(
        "class_teacher_assignments",
        params={"school_id": f"eq.{sid}", "select": "*", "order": "created_at.desc"},
    )


@router.post(
    "/{school_id}/class-teacher-assignments",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_class_teacher_assignment(
    school_id: str, body: ClassTeacherAssignmentCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "class_teacher_assignments",
        {"school_id": str(sid), **body.model_dump(mode="json")},
    )
    return rows[0]
