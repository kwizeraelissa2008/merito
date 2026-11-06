from decimal import Decimal

import pytest

from app.services.imports import (
    parse_csv,
    preview_from_csv,
    preview_import,
    weights_sum_to_one,
)


def test_parse_csv_handles_bom_and_blank_lines():
    text = "\ufeffname,code,category\nMathematics,MATH,core\n\n,,\nEnglish,ENG,core\n"
    headers, rows = parse_csv(text)
    assert headers == ["name", "code", "category"]
    assert len(rows) == 2
    assert rows[0]["code"] == "MATH"


def test_subjects_import_flags_missing_and_duplicates():
    text = (
        "name,code,category\n"
        "Mathematics,MATH,core\n"
        "Maths again,MATH,core\n"
        ",EMPTY,core\n"
        "Bad Category,BAD,nonsense\n"
    )
    _, preview = preview_from_csv("subjects", text)
    assert preview.total_rows == 4
    # First row ok
    assert preview.rows[0].status == "ok"
    # Duplicate code within file
    assert preview.rows[1].status == "error"
    assert any("duplicate code" in m for m in preview.rows[1].messages)
    # Missing name
    assert preview.rows[2].status == "error"
    # Invalid category
    assert preview.rows[3].status == "error"


def test_subjects_import_warns_on_existing_code():
    rows = [{"name": "Mathematics", "code": "MATH", "category": "core"}]
    result = preview_import("subjects", rows, existing_keys={"MATH"})
    assert result.rows[0].status == "warning"
    assert "already exists" in result.rows[0].messages[0]


def test_missing_required_column_raises():
    with pytest.raises(ValueError, match="Missing required column"):
        preview_from_csv("classes", "name,grade\nS1A,S1\n")


def test_students_import_requires_unique_codes():
    text = (
        "student_code,full_name,gender\n"
        "S1-001,Alice Uwase,female\n"
        "S1-001,Duplicate Person,male\n"
        "S1-002,Bob Nkurunziza,\n"
    )
    _, preview = preview_from_csv("students", text)
    assert preview.rows[0].status == "ok"
    assert preview.rows[1].status == "error"
    assert preview.rows[2].status == "ok"


def test_classes_import_validates_required_columns():
    text = "name,grade,academic_year\nS1A,S1,2025-2026\nS1B,,2025-2026\n"
    _, preview = preview_from_csv("classes", text)
    assert preview.rows[0].status == "ok"
    assert preview.rows[1].status == "error"


def test_weights_sum_to_one_tolerance():
    assert weights_sum_to_one([Decimal("0.4"), Decimal("0.6")])
    assert weights_sum_to_one([Decimal("0.3333"), Decimal("0.3333"), Decimal("0.3334")])
    assert not weights_sum_to_one([Decimal("0.4"), Decimal("0.5")])


def test_unsupported_entity_raises():
    with pytest.raises(ValueError, match="Unsupported import entity"):
        preview_import("teachers", [])
