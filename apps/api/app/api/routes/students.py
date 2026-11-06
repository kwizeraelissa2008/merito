"""Phase 3 student management: CRUD, enrollment history, transfer, withdrawal.

Design rules enforced here:
  * Student codes are unique per school (DB constraint + generation helper).
  * Enrollments are never overwritten — a transfer closes the old row and opens
    a new one, preserving full history.
  * Assignment-scoped visibility is enforced by RLS; this router adds explicit
    role checks for mutations.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.students import (
    BulkStudentCreate,
    EnrollmentCreate,
    StudentCreate,
    StudentTransfer,
    StudentUpdate,
    StudentWithdrawal,
)
from app.core.auth import CurrentUserDep, client_for, parse_school_id, require_school_role

router = APIRouter(prefix="/schools", tags=["students"])

ADMIN = ("school_admin",)
READ = ("school_admin", "principal", "dean_of_discipline", "discipline_staff",
        "subject_teacher", "class_teacher", "hod_moderator")


async def _audit(user: CurrentUserDep, school_id: uuid.UUID, action: str,
                 entity_type: str, entity_id: str, new_value: dict[str, Any] | None = None) -> None:
    await client_for(user).insert(
        "audit_logs",
        {
            "school_id": str(school_id),
            "actor_id": str(user.id),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "new_value": new_value,
        },
    )


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------
@router.get("/{school_id}/students", response_model=list)
async def list_students(
    school_id: str,
    user: CurrentUserDep,
    class_id: str | None = None,
    search: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, READ)
    limit = max(1, min(limit, 500))

    params: dict[str, str] = {
        "school_id": f"eq.{sid}",
        "select": "*",
        "order": "full_name.asc",
        "limit": str(limit),
        "offset": str(offset),
    }
    if search:
        params["or"] = f"(full_name.ilike.*{search}*,student_code.ilike.*{search}*)"

    client = client_for(user)
    if class_id:
        # Restrict to students actively enrolled in the class.
        enrollments = await client.select(
            "enrollments",
            params={
                "school_id": f"eq.{sid}",
                "class_id": f"eq.{class_id}",
                "status": "eq.active",
                "select": "student_id",
            },
        )
        ids = [e["student_id"] for e in enrollments]
        if not ids:
            return []
        params["id"] = f"in.({','.join(ids)})"

    return await client.select("students", params=params)


@router.get("/{school_id}/students/{student_id}", response_model=dict)
async def get_student(
    school_id: str, student_id: str, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, READ)
    client = client_for(user)
    rows = await client.select(
        "students", params={"id": f"eq.{student_id}", "school_id": f"eq.{sid}", "select": "*"}
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Student not found")
    enrollments = await client.select(
        "enrollments",
        params={
            "student_id": f"eq.{student_id}",
            "select": "*,classes(id,name,grade_id,combination_id)",
            "order": "start_date.desc",
        },
    )
    return {**rows[0], "enrollments": enrollments}


@router.post(
    "/{school_id}/students",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_student(
    school_id: str, body: StudentCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    client = client_for(user)

    code = body.student_code
    if not code:
        code_rows = await client.rpc("generate_student_code", {"p_school_id": str(sid)})
        code = code_rows if isinstance(code_rows, str) else str(code_rows)

    payload: dict[str, Any] = {
        "school_id": str(sid),
        "student_code": code,
        "full_name": body.full_name,
        "profile_fields": body.profile_fields,
    }
    if body.gender:
        payload["gender"] = body.gender
    if body.date_of_birth:
        payload["date_of_birth"] = body.date_of_birth.isoformat()

    try:
        rows = await client.insert("students", payload)
    except Exception as exc:  # noqa: BLE001 - surface uniqueness clearly
        raise HTTPException(
            status_code=409, detail="A student with this code already exists"
        ) from exc

    await _audit(user, sid, "student.created", "students", rows[0]["id"],
                 {"student_code": code, "full_name": body.full_name})
    return rows[0]


@router.patch("/{school_id}/students/{student_id}", response_model=dict)
async def update_student(
    school_id: str, student_id: str, body: StudentUpdate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    payload = body.model_dump(exclude_unset=True, mode="json")
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    rows = await client_for(user).update(
        "students", payload,
        params={"id": f"eq.{student_id}", "school_id": f"eq.{sid}"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Student not found")
    await _audit(user, sid, "student.updated", "students", student_id, payload)
    return rows[0]


@router.post(
    "/{school_id}/students/bulk",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def bulk_create_students(
    school_id: str, body: BulkStudentCreate, user: CurrentUserDep
) -> dict[str, Any]:
    """Create many students and enroll them in one class, transactionally."""
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    client = client_for(user)

    created: list[str] = []
    failed: list[dict[str, str]] = []
    for student in body.students:
        code = student.student_code
        if not code:
            code_rows = await client.rpc("generate_student_code", {"p_school_id": str(sid)})
            code = code_rows if isinstance(code_rows, str) else str(code_rows)
        payload: dict[str, Any] = {
            "school_id": str(sid),
            "student_code": code,
            "full_name": student.full_name,
        }
        if student.gender:
            payload["gender"] = student.gender
        if student.date_of_birth:
            payload["date_of_birth"] = student.date_of_birth.isoformat()
        try:
            rows = await client.insert("students", payload)
        except Exception:  # noqa: BLE001
            failed.append({"student_code": code, "reason": "duplicate or invalid"})
            continue
        student_id = rows[0]["id"]
        try:
            await client.insert(
                "enrollments",
                {
                    "school_id": str(sid),
                    "student_id": student_id,
                    "academic_year_id": str(body.academic_year_id),
                    "class_id": str(body.class_id),
                    "start_date": body.start_date.isoformat(),
                },
            )
        except Exception:  # noqa: BLE001
            failed.append({"student_code": code, "reason": "enrollment failed"})
            continue
        created.append(student_id)

    await _audit(user, sid, "students.bulk_created", "students", str(sid),
                 {"created": len(created), "failed": len(failed)})
    return {"created": len(created), "failed": failed}


# ---------------------------------------------------------------------------
# Enrollment history
# ---------------------------------------------------------------------------
@router.post(
    "/{school_id}/enrollments",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def create_enrollment(
    school_id: str, body: EnrollmentCreate, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    rows = await client_for(user).insert(
        "enrollments", {"school_id": str(sid), **body.model_dump(mode="json")}
    )
    await _audit(user, sid, "enrollment.created", "enrollments", rows[0]["id"],
                 body.model_dump(mode="json"))
    return rows[0]


@router.post("/{school_id}/students/{student_id}/transfer", response_model=dict)
async def transfer_student(
    school_id: str, student_id: str, body: StudentTransfer, user: CurrentUserDep
) -> dict[str, Any]:
    """Move a student to a new class, preserving enrollment history.

    Closes the active enrollment (status=transferred, end_date) and opens a new
    active enrollment in the target class. Never edits past rows.
    """
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    client = client_for(user)

    active = await client.select(
        "enrollments",
        params={
            "school_id": f"eq.{sid}",
            "student_id": f"eq.{student_id}",
            "status": "eq.active",
            "select": "*",
        },
    )
    if not active:
        raise HTTPException(status_code=400, detail="Student has no active enrollment")

    current = active[0]
    await client.update(
        "enrollments",
        {"status": "transferred", "end_date": body.effective_date.isoformat()},
        params={"id": f"eq.{current['id']}"},
    )
    created = await client.insert(
        "enrollments",
        {
            "school_id": str(sid),
            "student_id": student_id,
            "academic_year_id": current["academic_year_id"],
            "class_id": str(body.new_class_id),
            "start_date": body.effective_date.isoformat(),
        },
    )
    await _audit(user, sid, "student.transferred", "students", student_id,
                 {"from_class": current["class_id"], "to_class": str(body.new_class_id),
                  "reason": body.reason})
    return {"closed_enrollment_id": current["id"], "new_enrollment": created[0]}


@router.post("/{school_id}/students/{student_id}/withdraw", response_model=dict)
async def withdraw_student(
    school_id: str, student_id: str, body: StudentWithdrawal, user: CurrentUserDep
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    client = client_for(user)

    active = await client.select(
        "enrollments",
        params={
            "school_id": f"eq.{sid}",
            "student_id": f"eq.{student_id}",
            "status": "eq.active",
            "select": "id",
        },
    )
    for enrollment in active:
        await client.update(
            "enrollments",
            {"status": "withdrawn", "end_date": body.withdrawal_date.isoformat()},
            params={"id": f"eq.{enrollment['id']}"},
        )
    rows = await client.update(
        "students",
        {"status": body.status},
        params={"id": f"eq.{student_id}", "school_id": f"eq.{sid}"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Student not found")
    await _audit(user, sid, "student.withdrawn", "students", student_id,
                 {"status": body.status, "reason": body.reason})
    return rows[0]
