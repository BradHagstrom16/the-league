from pull_league_data import rank_standings


def _row(rid, wins, losses, pf):
    return {"roster_id": rid, "wins": wins, "losses": losses, "ties": 0,
            "points_for": pf, "finish": "", "made_playoffs": ""}


def test_complete_season_ranks_by_wins_then_points_for():
    rows = [_row(1, 9, 5, 1500.0), _row(2, 10, 4, 1400.0), _row(3, 9, 5, 1600.0)]
    ranked = rank_standings(rows, playoff_teams=2, status="complete")
    assert [r["roster_id"] for r in ranked] == [2, 3, 1]
    assert [r["finish"] for r in ranked] == [1, 2, 3]
    assert [r["made_playoffs"] for r in ranked] == [1, 1, 0]


def test_in_progress_season_gets_no_finish():
    # Week 4 of 2026: real records, but nobody has finished anything. A finish
    # here made the stats code treat 2026 as concluded with no champion, which
    # broke validation and the home page from 2026-09-15 on.
    rows = [_row(1, 3, 0, 388.8), _row(2, 0, 3, 332.2)]
    for status in ("in_season", "post_season"):
        ranked = rank_standings([dict(r) for r in rows], playoff_teams=6, status=status)
        assert all(r["finish"] == "" and r["made_playoffs"] == "" for r in ranked)


def test_unplayed_season_gets_no_finish():
    rows = [_row(1, 0, 0, 0.0), _row(2, 0, 0, 0.0)]
    for status in ("pre_draft", "drafting"):
        ranked = rank_standings([dict(r) for r in rows], playoff_teams=6, status=status)
        assert all(r["finish"] == "" for r in ranked)
