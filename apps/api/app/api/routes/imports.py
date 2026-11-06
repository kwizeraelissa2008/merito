"""Phase 2 configuration import endpoints: preview then commit.

Two-step flow:
  1. POST ``/imports/{entity}/preview`` with CSV text → per-row validation result.
  2. POST ``/imports/{entity}/commit`` with the corrected rows → audited insert.

Nothing is written during preview. Rows carrying errors are refused at commit.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.schemas.configuration import ImportCommitRequest, ImportPreviewResponse
from app.core.auth import CurrentUserDep, client_for, parse_school_id, require_school_role
from app.services.imports import preview_from_csv, preview_import

router = APIRouter(prefix="/schools", tags=["imports"])

ADMIN = ("school_admin",)


async def _existing_keys(school_id: uuid.UUID, entity: str, user: CurrentUserDep) -> set[str]:
    client = client_for(user)
    if entity == "subjects":
        rows = await client.select(
            "subjects", params={"school_id": f"eq.{school_id}", "select": "code"}
        )
        return {str(r["code"]) for r in rows}
    if entity == "classes":
        rows = await client.select(
            "classes", params={"school_id": f"eq.{school_id}", "select": "name"}
        )
        return {str(r["name"]) for r in rows}
    rows = await client.select(
        "students", params={"school_id": f"eq.{school_id}", "select": "student_code"}
    )
    return {str(r["student_code"]) for r in rows}


@router.post("/{school_id}/imports/{entity}/preview", response_model=ImportPreviewResponse)
async def preview_configuration_import(
    school_id: str,
    entity: str,
    body: dict[str, str],
    user: CurrentUserDep,
) -> ImportPreviewResponse:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    csv_text = body.get("csv", "")
    if not csv_text.strip():
        raise HTTPException(status_code=400, detail="csv content is required")
    existing = await _existing_keys(sid, entity, user)
    try:
        _, preview = preview_from_csv(entity, csv_text, existing_keys=existing)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ImportPreviewResponse(
        entity=preview.entity,
        total_rows=preview.total_rows,
        ok_rows=preview.ok_rows,
        warning_rows=preview.warning_rows,
        error_rows=preview.error_rows,
        rows=[
            {
                "row_number": r.row_number,
                "status": r.status,
                "messages": r.messages,
                "data": r.data,
            }
            for r in preview.rows
        ],
    )


@router.post("/{school_id}/imports/{entity}/commit")
async def commit_configuration_import(
    school_id: str,
    entity: str,
    body: ImportCommitRequest,
    user: CurrentUserDep,
) -> dict[str, Any]:
    sid = parse_school_id(school_id)
    await require_school_role(user, sid, ADMIN)
    if body.entity != entity:
        raise HTTPException(status_code=400, detail="Entity mismatch between path and body")

    existing = await _existing_keys(sid, entity, user)
    # Normalise keys to the entity's identifier column for revalidation.
    key_for = {"subjects": "code", "classes": "name", "students": "student_code"}[entity]
    normalised = []
    for row in body.rows:
        if entity == "subjects":
            normalised.append(
                {
                    "name": str(row.get("name", "")),
                    "code": str(row.get("code", "")),
                    "category": str(row.get("category", "core")),
                }
            )
        elif entity == "students":
            normalised.append(
                {
                    "student_code": str(row.get("student_code", "")),
                    "full_name": str(row.get("full_name", "")),
                    "gender": str(row.get("gender", "")),
                    "date_of_birth": str(row.get("date_of_birth", "")),
                }
            )
        else:
            normalised.append(
                {
                    "name": str(row.get("name", "")),
                    "grade": str(row.get("grade", "")),
                    "academic_year": str(row.get("academic_year", "")),
                }
            )

    preview = preview_import(entity, normalised, existing_keys=existing)
    blocking = [r for r in preview.rows if r.status == "error"]
    if blocking:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Some rows still contain errors and were not imported",
                "rows": [
                    {"row_number": r.row_number, "messages": r.messages} for r in blocking
                ],
            },
        )

    client = client_for(user)
    to_insert = [r.data for r in preview.rows if r.status != "error"]
    inserted = 0

    if entity == "subjects":
        payload = [
            {"school_id": str(sid), "name": d["name"], "code": d["code"],
             "category": d["category"]}
            for d in to_insert
        ]
        if payload:
            rows = await client.insert("subjects", payload)
            inserted = len(rows)
    elif entity == "students":
        payload = [
            {
                "school_id": str(sid),
                "student_code": d["student_code"],
                "full_name": d["full_name"],
                **({"gender": d["gender"]} if d.get("gender") else {}),
                **({"date_of_birth": d["date_of_birth"]} if d.get("date_of_birth") else {}),
            }
            for d in to_insert
        ]
        if payload:
            rows = await client.insert("students", payload)
            inserted = len(rows)
    else:
        # Classes require resolving grade + academic year names to ids.
        grades = await client.select(
            "grades", params={"school_id": f"eq.{sid}", "select": "id,name"}
        )
        years = await client.select(
            "academic_years", params={"school_id": f"eq.{sid}", "select": "id,name"}
        )
        grade_by_name = {g["name"]: g["id"] for g in grades}
        year_by_name = {y["name"]: y["id"] for y in years}
        payload = []
        for d in to_insert:
            grade_id = grade_by_name.get(d["grade"])
            year_id = year_by_name.get(d["academic_year"])
            if not grade_id or not year_id:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown grade '{d['grade']}' or academic year '{d['academic_year']}'",
                )
            payload.append(
                {
                    "school_id": str(sid),
                    "academic_year_id": year_id,
                    "grade_id": grade_id,
                    "name": d["name"],
                }
            )
        if payload:
            rows = await client.insert("classes", payload)
            inserted = len(rows)

    await client.insert(
        "audit_logs",
        {
            "school_id": str(sid),
            "actor_id": str(user.id),
            "action": f"import.{entity}",
            "entity_type": entity,
            "new_value": {"inserted": inserted, "key_column": key_for},
        },
    )
    return {"entity": entity, "inserted": inserted, "skipped": len(body.rows) - inserted}
