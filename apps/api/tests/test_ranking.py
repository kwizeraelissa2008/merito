from decimal import Decimal

from app.calculations.ranking import RankEntry, rank_scores


def test_shared_positions_for_ties():
    results = rank_scores(
        [
            RankEntry(entity_id="a", score=Decimal("90")),
            RankEntry(entity_id="b", score=Decimal("85")),
            RankEntry(entity_id="c", score=Decimal("85")),
            RankEntry(entity_id="d", score=Decimal("70")),
        ]
    )
    by_id = {r.entity_id: r.position for r in results}
    assert by_id == {"a": 1, "b": 2, "c": 2, "d": 4}


def test_ineligible_excluded_from_rank():
    results = rank_scores(
        [
            RankEntry(entity_id="a", score=Decimal("90"), eligible=True),
            RankEntry(entity_id="b", score=Decimal("99"), eligible=False),
        ]
    )
    by_id = {r.entity_id: r.position for r in results}
    assert by_id["a"] == 1
    assert by_id["b"] is None