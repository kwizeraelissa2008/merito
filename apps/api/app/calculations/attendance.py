"""Attendance aggregation helpers."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from pydantic import BaseModel


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"
    OTHER = "other"


class AttendanceSummary(BaseModel):
    school_days: int
    present: int
    absent: int
    late: int
    excused: int
    other: int
    missing_records: int
    attendance_percentage: Decimal | None


def attendance_summary(
    statuses: list[AttendanceStatus | None],
    *,
    count_late_as_present: bool = True,
    places: int = 2,
) -> AttendanceSummary:
    """`None` entries are missing records (distinct from confirmed absence)."""
    present = absent = late = excused = other = missing = 0
    for s in statuses:
        if s is None:
            missing += 1
            continue
        if s == AttendanceStatus.PRESENT:
            present += 1
        elif s == AttendanceStatus.ABSENT:
            absent += 1
        elif s == AttendanceStatus.LATE:
            late += 1
        elif s == AttendanceStatus.EXCUSED:
            excused += 1
        else:
            other += 1

    school_days = len(statuses) - missing
    attended = present + (late if count_late_as_present else 0)
    pct: Decimal | None
    if school_days == 0:
        pct = None
    else:
        raw = (Decimal(attended) / Decimal(school_days)) * Decimal("100")
        pct = raw.quantize(Decimal("1").scaleb(-places), rounding=ROUND_HALF_UP)

    return AttendanceSummary(
        school_days=school_days,
        present=present,
        absent=absent,
        late=late,
        excused=excused,
        other=other,
        missing_records=missing,
        attendance_percentage=pct,
    )