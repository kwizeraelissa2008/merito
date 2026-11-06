"""Phase 3 assessments and mark entry.

Endpoints:
  * Create/list/update assessments for a class+subject+reporting period.
  * Fetch a mark grid (students × assessments) for autosave rendering.
  * Autosave a single cell with optimistic concurrency (version check).
  * Bulk-save a grid atomically; a single stale version rejects the whole batch.
  * Submit / review a mark sheet (teacher → HoD/principal workflow).

Authorisation is assignment-scoped: a teacher may only touch assessments and
scores for classes+subjects they actually teach (enforced here and by RLS).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.students import (
    AssessmentCreate,
    AssessmentUpdate,
    BulkScoreResult,
    BulkScoreUpsert,
    MarkSheetReview,
    MarkSheetSubmit,
    ScoreConflict,
    ScoreUpsert,
)
from app.core.auth import CurrentUserDep, client_for, parse_school_id, require_school_role
from app.core.supabase import service_client

router = APIRouter(prefix="/schools", tags=["marks"])

ADMIN = ("school_admin",)
TEACHER_ROLES = ("subject_teacher", "class_teacher", "hod_moderator")
LEADERSHIP = ("school_admin", "principal", "dean_of_discipline", "hod_moderator")


async def _ensure_teaches(
    user: CurrentUserDep, school_id: uuid.UUID, class_id: str, subject_id: str
) -> None:
    """Raise 403 unless the caller teaches this class+subject (or is admin)."""
    rows = await service_client().select(
        "school_memberships",
        params={
            "school_id": f"eq.{school_id}",
            "user_id": f"eq.{user.id}",
            "status": "eq.active",
            "select": "role",
        },
    )
    roles = {r["role"] for r in rows}
    if "school_admin" in roles:
        return
    assignments = await client_for(user).select(
        "teaching_assignments",
        params={
            "school_id": f"eq.{school_id}",
            "class_id": f"eq.{class_id}",
            "subject_id": f"eq.{subject_id}",
            "teacher_user_id": f"eq.{user.id}",
            "active": "eq.true",
            "select": "id",
        },
    )
    if not assignments:
        raise HTTPException(
            status_code=403,
            detail="You are not assigned to teach this subject in this class",
        )


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------
@router.get("/{school_id}/assessments", response_model=list)
async def list_assessments(
    school_id: str,
    user: CurrentUserDep,
    class_id: str | None = None,
    subject_id: str | None = None,
    reporting_period_id: str | None = None,
) -> list[dict[str, Any]]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN + TEACHER_ROLES + LEADERSHIP)
    params: dict[str, str] = {"school_id": f"eq.{sid}", "select": "*", "order": "created_at.asc"}
    if class_id:
        params["class_id"] = f"eq.{class_id}"
    if subject_id:
        params["subject_id"] = f"eq.{subject_id}"
    if reporting_period_id:
        params["reporting_period_id"] = f"eq.{reporting_period_id}"
    return await client_for(user).select("assessments", params=params)


@router.post(
    "/{school_id}/assessments",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_assessment(
    school_id: str, body: AssessmentCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await _ensure_teaches(user, sid, str(body.class_id), str(body.subject_id))
    rows = await client_for(user).insert(
        "assessments",
        {
            "school_id": str(sid),
            "created_by": str(user.id),
            **body.model_dump(mode="json"),
        },
    )
    await client_for(user).insert(
        "audit_logs",
        {
            "school_id": str(sid),
            "actor_id": str(user.id),
            "action": "assessment.created",
            "entity_type": "assessments",
            "entity_id": rows[0]["id"],
            "new_value": body.model_dump(mode="json"),
        },
    )
    return rows[0]


@router.patch("/{school_id}/assessments/{assessment_id}", response_model=dict)
async def update_assessment(
    school_id: str, assessment_id: str, body: AssessmentUpdate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    client = client_for(user)
    existing = await client.select(
        "assessments",
        params={"id": f"eq.{assessment_id}", "school_id": f"eq.{sid}", "select": "*"},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Assessment not found")
    assessment = existing[0]
    await _ensure_teaches(user, sid, assessment["class_id"], assessment["subject_id"])

    payload = body.model_dump(exclude_unset=True, mode="json")
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Lowering the maximum below an existing score would corrupt data — block it.
    if "maximum_marks" in payload:
        scores = await client.select(
            "assessment_scores",
            params={
                "assessment_id": f"eq.{assessment_id}",
                "status": "eq.scored",
                "select": "score",
            },
        )
        highest = max((Decimal(str(s["score"])) for s in scores), default=Decimal("0"))
        if Decimal(str(payload["maximum_marks"])) < highest:
            raise HTTPException(
                status_code=422,
                detail=f"New maximum is below an existing score ({highest})",
            )
    rows = await client.update(
        "assessments", payload, params={"id": f"eq.{assessment_id}"}
    )
    return rows[0]


# ---------------------------------------------------------------------------
# Mark grid
# ---------------------------------------------------------------------------
@router.get("/{school_id}/mark-grid", response_model=dict)
async def get_mark_grid(
    school_id: str,
    user: CurrentUserDep,
    reporting_period_id: str,
    class_id: str,
    subject_id: str,
) -> dict[str, Any]:
    """Return everything the spreadsheet grid needs: roster + assessments + scores."""
    sid = parse_school_id(school_id)
    await _ensure_teaches(user, sid, class_id, subject_id)
    client = client_for(user)

    roster = await client.select(
        "enrollments",
        params={
            "school_id": f"eq.{sid}",
            "class_id": f"eq.{class_id}",
            "status": "eq.active",
            "select": "student_id,students(id,student_code,full_name)",
        },
    )
    students = []
    for row in roster:
        student = row.get("students")
        if isinstance(student, list):
            student = student[0] if student else None
        if student:
            students.append(student)
    students.sort(key=lambda s: s["full_name"])

    assessments = await client.select(
        "assessments",
        params={
            "school_id": f"eq.{sid}",
            "reporting_period_id": f"eq.{reporting_period_id}",
            "class_id": f"eq.{class_id}",
            "subject_id": f"eq.{subject_id}",
            "select": "*",
            "order": "created_at.asc",
        },
    )

    assessment_ids = [a["id"] for a in assessments]
    scores: list[dict[str, Any]] = []
    if assessment_ids:
        scores = await client.select(
            "assessment_scores",
            params={
                "assessment_id": f"in.({','.join(assessment_ids)})",
                "select": "id,assessment_id,student_id,score,status,version,updated_at",
            },
        )

    marksheet = await client.select(
        "marksheets",
        params={
            "school_id": f"eq.{sid}",
            "reporting_period_id": f"eq.{reporting_period_id}",
            "class_id": f"eq.{class_id}",
            "subject_id": f"eq.{subject_id}",
            "select": "*",
        },
    )

    return {
        "students": students,
        "assessments": assessments,
        "scores": scores,
        "marksheet": marksheet[0] if marksheet else None,
    }


# ---------------------------------------------------------------------------
# Autosave a single cell (optimistic concurrency)
# ---------------------------------------------------------------------------
@router.put("/{school_id}/scores", response_model=dict)
async def upsert_score(
    school_id: str, body: ScoreUpsert, user: CurrentUserDep
) -> dict[str, Any]:
    """Autosave one cell.

    Optimistic concurrency: when `version` is supplied, the write is rejected
    (409) if the stored version differs — the caller keeps the user's input and
    presents the server value.
    """
    sid = parse_school_id(school_id)
    client = client_for(user)

    assessment = await client.select(
        "assessments",
        params={"id": f"eq.{body.assessment_id}", "school_id": f"eq.{sid}", "select": "*"},
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    a = assessment[0]
    await _ensure_teaches(user, sid, a["class_id"], a["subject_id"])

    if body.status == "scored":
        if body.score is None:
            raise HTTPException(status_code=422, detail="score required when scored")
        if body.score > Decimal(str(a["maximum_marks"])):
            raise HTTPException(
                status_code=422,
                detail=f"Score {body.score} exceeds maximum {a['maximum_marks']}",
            )

    existing = await client.select(
        "assessment_scores",
        params={
            "assessment_id": f"eq.{body.assessment_id}",
            "student_id": f"eq.{body.student_id}",
            "select": "*",
        },
    )

    payload = {
        "score": str(body.score) if body.score is not None else None,
        "status": body.status,
        "updated_by": str(user.id),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if not existing:
        rows = await client.insert(
            "assessment_scores",
            {
                "school_id": str(sid),
                "assessment_id": str(body.assessment_id),
                "student_id": str(body.student_id),
                **payload,
            },
        )
        return rows[0]

    current = existing[0]
    if body.version is not None and body.version != current["version"]:
        raise HTTPException(
            status_code=409,
            detail=_conflict_detail(body, current),
        )
    rows = await client.update(
        "assessment_scores",
        {**payload, "version": current["version"]},
        params={"id": f"eq.{current['id']}"},
    )
    return rows[0]


def _conflict_detail(body: ScoreUpsert, current: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": "version_conflict",
        "message": "This score was changed by someone else. Your input is preserved.",
        "expected_version": body.version,
        "current_version": current["version"],
        "current_score": current["score"],
        "current_status": current["status"],
    }


# ---------------------------------------------------------------------------
# Bulk save (atomic)
# ---------------------------------------------------------------------------
@router.post("/{school_id}/scores/bulk", response_model=BulkScoreResult)
async def bulk_upsert_scores(
    school_id: str, body: BulkScoreUpsert, user: CurrentUserDep
) -> BulkScoreResult:
    """Save a whole grid in one request.

    All rows are validated first. If ANY row has a stale version the entire
    batch is rejected with the list of conflicts and nothing is written — the
    client shows the diffs and lets the user resolve them.
    """
    sid = parse_school_id(school_id)
    client = client_for(user)

    cache: dict[str, dict[str, Any]] = {}
    conflicts: list[ScoreConflict] = []
    to_write: list[tuple[dict[str, Any], dict[str, Any] | None]] = []

    for item in body.scores:
        aid = str(item.assessment_id)
        if aid not in cache:
            rows = await client.select(
                "assessments",
                params={"id": f"eq.{aid}", "school_id": f"eq.{sid}", "select": "*"},
            )
            if not rows:
                raise HTTPException(status_code=404, detail=f"Assessment {aid} not found")
            cache[aid] = rows[0]
        a = cache[aid]
        await _ensure_teaches(user, sid, a["class_id"], a["subject_id"])

        if item.status == "scored":
            if item.score is None:
                raise HTTPException(status_code=422, detail="score required when scored")
            if item.score > Decimal(str(a["maximum_marks"])):
                raise HTTPException(
                    status_code=422,
                    detail=f"Score {item.score} exceeds maximum {a['maximum_marks']}",
                )

        existing = await client.select(
            "assessment_scores",
            params={
                "assessment_id": f"eq.{aid}",
                "student_id": f"eq.{item.student_id}",
                "select": "*",
            },
        )
        current = existing[0] if existing else None
        if current and item.version is not None and item.version != current["version"]:
            conflicts.append(
                ScoreConflict(
                    assessment_id=item.assessment_id,
                    student_id=item.student_id,
                    expected_version=item.version,
                    current_version=current["version"],
                    current_score=current["score"],
                    current_status=current["status"],
                )
            )
            continue
        to_write.append((current, {"item": item, "assessment": a}))

    if conflicts:
        # Nothing written — caller resolves and retries.
        return BulkScoreResult(applied=0, conflicts=conflicts)

    applied = 0
    for current, ctx in to_write:
        item: ScoreUpsert = ctx["item"]
        payload = {
            "score": str(item.score) if item.score is not None else None,
            "status": item.status,
            "updated_by": str(user.id),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if current:
            await client.update(
                "assessment_scores",
                {**payload, "version": current["version"]},
                params={"id": f"eq.{current['id']}"},
            )
        else:
            await client.insert(
                "assessment_scores",
                {
                    "school_id": str(sid),
                    "assessment_id": str(item.assessment_id),
                    "student_id": str(item.student_id),
                    **payload,
                },
            )
        applied += 1

    return BulkScoreResult(applied=applied, conflicts=[])


# ---------------------------------------------------------------------------
# Mark sheet submission workflow
# ---------------------------------------------------------------------------
@router.post("/{school_id}/marksheets/submit", response_model=dict)
async def submit_marksheet(
    school_id: str, body: MarkSheetSubmit, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await _ensure_teaches(user, sid, str(body.class_id), str(body.subject_id))
    client = client_for(user)

    existing = await client.select(
        "marksheets",
        params={
            "school_id": f"eq.{sid}",
            "reporting_period_id": f"eq.{body.reporting_period_id}",
            "class_id": f"eq.{body.class_id}",
            "subject_id": f"eq.{body.subject_id}",
            "select": "*",
        },
    )
    payload = {
        "status": "submitted",
        "submitted_by": str(user.id),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "review_note": body.comment or None,
    }
    if existing:
        if existing[0]["status"] in ("approved", "locked"):
            raise HTTPException(
                status_code=409,
                detail="This mark sheet is already approved or locked",
            )
        rows = await client.update("marksheets", payload, params={"id": f"eq.{existing[0]['id']}"})
    else:
        rows = await client.insert(
            "marksheets",
            {
                "school_id": str(sid),
                "reporting_period_id": str(body.reporting_period_id),
                "class_id": str(body.class_id),
                "subject_id": str(body.subject_id),
                **payload,
            },
        )
    await client.insert(
        "audit_logs",
        {
            "school_id": str(sid),
            "actor_id": str(user.id),
            "action": "marksheet.submitted",
            "entity_type": "marksheets",
            "entity_id": rows[0]["id"],
        },
    )
    return rows[0]


@router.post("/{school_id}/marksheets/{marksheet_id}/review", response_model=dict)
async def review_marksheet(
    school_id: str, marksheet_id: str, body: MarkSheetReview, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ("school_admin", "principal", "hod_moderator"))
    client = client_for(user)

    existing = await client.select(
        "marksheets",
        params={"id": f"eq.{marksheet_id}", "school_id": f"eq.{sid}", "select": "*"},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Mark sheet not found")
    if existing[0]["status"] != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted mark sheets can be reviewed")

    new_status = "approved" if body.decision == "approved" else "returned"
    rows = await client.update(
        "marksheets",
        {
            "status": new_status,
            "reviewed_by": str(user.id),
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "review_note": body.note or None,
        },
        params={"id": f"eq.{marksheet_id}"},
    )
    await client.insert(
        "audit_logs",
        {
            "school_id": str(sid),
            "actor_id": str(user.id),
            "action": f"marksheet.{new_status}",
            "entity_type": "marksheets",
            "entity_id": marksheet_id,
            "reason": body.note or None,
        },
    )
    return rows[0]
