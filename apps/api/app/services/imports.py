"""Configuration import (CSV/Excel-friendly) validation.

Pure functions: no database or network access, so they are trivially unit tested.
The router feeds rows through :func:`preview_import`, shows the result to the
user, then calls :func:`commit` (which performs the audited DB writes).

Rules:
  * Validate required columns and value domains.
  * Flag duplicates within the file and against existing records.
  * Never partially apply a row that has errors.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

SUPPORTED_ENTITIES = ("subjects", "classes", "students")

# Required columns per entity.
REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "subjects": ("name", "code", "category"),
    "classes": ("name", "grade", "academic_year"),
    "students": ("student_code", "full_name"),
}

VALID_SUBJECT_CATEGORIES = {"core", "minor", "optional", "other"}


@dataclass
class PreviewRow:
    row_number: int
    status: str  # ok | warning | error
    messages: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreviewResult:
    entity: str
    rows: list[PreviewRow]

    @property
    def total_rows(self) -> int:
        return len(self.rows)

    @property
    def ok_rows(self) -> int:
        return sum(1 for r in self.rows if r.status == "ok")

    @property
    def warning_rows(self) -> int:
        return sum(1 for r in self.rows if r.status == "warning")

    @property
    def error_rows(self) -> int:
        return sum(1 for r in self.rows if r.status == "error")


def parse_csv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV text into a header list and row dicts. Tolerant of BOM/blank lines."""
    text = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], []
    headers = [h.strip().lower() for h in reader.fieldnames]
    rows: list[dict[str, str]] = []
    for raw in reader:
        cleaned = {
            (k or "").strip().lower(): (v or "").strip() for k, v in raw.items() if k
        }
        if any(cleaned.values()):
            rows.append(cleaned)
    return headers, rows


def _validate_subject_row(
    row: dict[str, str], seen_codes: set[str], existing_codes: set[str]
) -> PreviewRow:
    messages: list[str] = []
    status = "ok"
    name = row.get("name", "").strip()
    code = row.get("code", "").strip().upper()
    category = (row.get("category", "").strip().lower()) or "core"

    if not name:
        messages.append("name is required")
        status = "error"
    if not code:
        messages.append("code is required")
        status = "error"
    if category not in VALID_SUBJECT_CATEGORIES:
        messages.append(
            f"category '{category}' must be one of {sorted(VALID_SUBJECT_CATEGORIES)}"
        )
        status = "error"
    if code and code in seen_codes:
        messages.append(f"duplicate code '{code}' within the file")
        status = "error"
    elif code and code in existing_codes:
        messages.append(f"subject code '{code}' already exists for this school")
        status = "warning"

    if code:
        seen_codes.add(code)

    return PreviewRow(
        row_number=row.get("__row__", 0),
        status=status,
        messages=messages,
        data={"name": name, "code": code, "category": category},
    )


def _validate_class_row(
    row: dict[str, str], seen_names: set[str], existing_names: set[str]
) -> PreviewRow:
    messages: list[str] = []
    status = "ok"
    name = row.get("name", "").strip()
    grade = row.get("grade", "").strip()
    academic_year = row.get("academic_year", "").strip()

    if not name:
        messages.append("name is required")
        status = "error"
    if not grade:
        messages.append("grade is required")
        status = "error"
    if not academic_year:
        messages.append("academic_year is required")
        status = "error"
    if name and name in seen_names:
        messages.append(f"duplicate class name '{name}' within the file")
        status = "error"
    elif name and name in existing_names:
        messages.append(f"class '{name}' already exists in this academic year")
        status = "warning"

    if name:
        seen_names.add(name)

    return PreviewRow(
        row_number=row.get("__row__", 0),
        status=status,
        messages=messages,
        data={
            "name": name,
            "grade": grade,
            "academic_year": academic_year,
            "combination": row.get("combination", "").strip() or None,
        },
    )


def _validate_student_row(
    row: dict[str, str], seen_codes: set[str], existing_codes: set[str]
) -> PreviewRow:
    messages: list[str] = []
    status = "ok"
    code = row.get("student_code", "").strip()
    full_name = row.get("full_name", "").strip()
    gender = row.get("gender", "").strip().lower() or None
    dob = row.get("date_of_birth", "").strip() or None

    if not code:
        messages.append("student_code is required")
        status = "error"
    if not full_name:
        messages.append("full_name is required")
        status = "error"
    if gender and gender not in {"male", "female", "other"}:
        messages.append("gender must be male, female, or other")
        status = "error"
    if code and code in seen_codes:
        messages.append(f"duplicate student_code '{code}' within the file")
        status = "error"
    elif code and code in existing_codes:
        messages.append(f"student code '{code}' already exists for this school")
        status = "error"

    if code:
        seen_codes.add(code)

    return PreviewRow(
        row_number=row.get("__row__", 0),
        status=status,
        messages=messages,
        data={
            "student_code": code,
            "full_name": full_name,
            "gender": gender,
            "date_of_birth": dob,
        },
    )


def preview_import(
    entity: str,
    rows: Iterable[dict[str, str]],
    existing_keys: set[str] | None = None,
) -> PreviewResult:
    """Validate rows for an entity.

    ``existing_keys`` lets the router flag conflicts with records already stored
    (subject codes, class names, or student codes depending on the entity).
    """
    if entity not in SUPPORTED_ENTITIES:
        raise ValueError(f"Unsupported import entity: {entity}")

    existing = existing_keys or set()
    seen: set[str] = set()
    out: list[PreviewRow] = []

    for index, row in enumerate(rows, start=2):  # row 1 is the header
        row = {**row, "__row__": index}  # type: ignore[assignment]
        if entity == "subjects":
            out.append(_validate_subject_row(row, seen, existing))
        elif entity == "classes":
            out.append(_validate_class_row(row, seen, existing))
        else:
            out.append(_validate_student_row(row, seen, existing))

    return PreviewResult(entity=entity, rows=out)


def preview_from_csv(
    entity: str, text: str, existing_keys: set[str] | None = None
) -> tuple[list[str], PreviewResult]:
    headers, rows = parse_csv(text)
    missing = [c for c in REQUIRED_COLUMNS[entity] if c not in headers]
    if missing:
        raise ValueError(
            f"Missing required column(s) for {entity}: {', '.join(missing)}"
        )
    return headers, preview_import(entity, rows, existing_keys)


def weights_sum_to_one(weights: Iterable[Decimal]) -> bool:
    """Return True when category weights sum to 1.0 (100%) within tolerance."""
    total = sum(weights, Decimal("0"))
    return abs(total - Decimal("1")) <= Decimal("0.0001")


def parse_decimal(value: str | None, *, default: Decimal | None = None) -> Decimal | None:
    if value is None or value == "":
        return default
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc
