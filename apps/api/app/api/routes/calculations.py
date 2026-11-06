from fastapi import APIRouter, HTTPException

from app.calculations.attendance import AttendanceStatus, attendance_summary
from app.calculations.behavior import behavior_score
from app.calculations.marks import CategoryInput, OverallResult, compute_overall_percentage
from app.calculations.ranking import RankEntry, RankResult, rank_scores
from pydantic import BaseModel, Field

router = APIRouter(prefix="/calculations", tags=["calculations"])


class MarksRequest(BaseModel):
    categories: list[CategoryInput]
    require_weights_sum_100: bool = True
    normalize_weights: bool = False
    allow_incomplete: bool = False
    display_places: int = 2


@router.post("/marks", response_model=OverallResult)
def post_marks(body: MarksRequest) -> OverallResult:
    try:
        return compute_overall_percentage(
            body.categories,
            require_weights_sum_100=body.require_weights_sum_100,
            normalize_weights=body.normalize_weights,
            allow_incomplete=body.allow_incomplete,
            display_places=body.display_places,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class BehaviorRequest(BaseModel):
    approved_deductions: list[str] = Field(
        description="Decimal strings for approved deductions"
    )
    base: str = "40"


@router.post("/behavior")
def post_behavior(body: BehaviorRequest):
    from decimal import Decimal

    try:
        return behavior_score(
            [Decimal(d) for d in body.approved_deductions],
            base=Decimal(body.base),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class AttendanceRequest(BaseModel):
    statuses: list[AttendanceStatus | None]
    count_late_as_present: bool = True


@router.post("/attendance")
def post_attendance(body: AttendanceRequest):
    return attendance_summary(
        body.statuses, count_late_as_present=body.count_late_as_present
    )


class RankRequest(BaseModel):
    entries: list[RankEntry]
    higher_is_better: bool = True


@router.post("/ranking", response_model=list[RankResult])
def post_ranking(body: RankRequest) -> list[RankResult]:
    return rank_scores(body.entries, higher_is_better=body.higher_is_better)