from leaguestats.recordbook import compute_records

_EXPECTED_KEYS = {
    "team_week_high", "team_week_low", "blowout", "nailbiter",
    "season_pf_high", "season_pf_low", "season_pa_high", "playoff_week_high",
    "win_streak", "loss_streak", "player_week_high", "player_season_high",
    "bench_week_high",
}


def test_records(tiny):
    out = compute_records(tiny)
    r = {x["key"]: x for x in out["records"]}
    assert r["team_week_high"]["value"] == 130.0 and r["team_week_high"]["holder"] == "Al"
    assert r["blowout"]["value"] == 60.0
    assert r["nailbiter"]["value"] == 1.0 and r["nailbiter"]["holder"] == "Cy"
    assert r["season_pf_high"]["value"] == 345.0
    assert r["season_pa_high"]["value"] == 315.0 and r["season_pa_high"]["holder"] == "Di"
    assert r["playoff_week_high"]["value"] == 100.0
    assert r["player_week_high"]["value"] == 35.0
    assert r["bench_week_high"]["value"] == 28.0 and r["bench_week_high"]["holder"] == "Al"
    assert r["win_streak"]["value"] == 3 and r["win_streak"]["holder"] == "Cy"


def test_all_keys_present_and_shaped(tiny):
    out = compute_records(tiny)
    r = {x["key"]: x for x in out["records"]}
    assert set(r) == _EXPECTED_KEYS
    for rec in out["records"]:
        assert set(rec) == {"key", "label", "value", "holder", "user_id", "detail"}
        assert isinstance(rec["label"], str) and rec["label"]
        assert isinstance(rec["detail"], str) and rec["detail"]


def test_team_week_low_and_details(tiny):
    r = {x["key"]: x for x in compute_records(tiny)["records"]}
    low = r["team_week_low"]
    assert low["value"] == 70.0 and low["holder"] == "Di" and low["user_id"] == "u4"
    assert low["detail"] == "Week 3, 2024 vs Al"

    high = r["team_week_high"]
    assert high["detail"] == "Week 3, 2024 vs Di"

    blowout = r["blowout"]
    assert blowout["holder"] == "Al" and blowout["detail"] == "Week 3, 2024 vs Di"

    nailbiter = r["nailbiter"]
    assert nailbiter["detail"] == "Week 3, 2024 vs Bo"


def test_season_records(tiny):
    r = {x["key"]: x for x in compute_records(tiny)["records"]}
    assert r["season_pf_low"]["value"] == 235.0 and r["season_pf_low"]["holder"] == "Di"
    assert r["season_pf_high"]["detail"] == "2024 season"
    assert r["season_pa_high"]["detail"] == "2024 season"


def test_playoff_week_high_detail(tiny):
    r = {x["key"]: x for x in compute_records(tiny)["records"]}
    p = r["playoff_week_high"]
    assert p["holder"] == "Al" and p["user_id"] == "u1"
    assert p["detail"] == "Week 4, 2024 vs Cy"
    assert "playoff" in p["label"].lower()


def test_streaks(tiny):
    r = {x["key"]: x for x in compute_records(tiny)["records"]}
    win = r["win_streak"]
    assert win["value"] == 3 and win["holder"] == "Cy" and isinstance(win["value"], int)
    assert win["detail"] == "Weeks 1-3, 2024"

    loss = r["loss_streak"]
    assert loss["value"] == 3 and loss["holder"] == "Di" and isinstance(loss["value"], int)
    assert loss["detail"] == "Weeks 1-3, 2024"


def test_player_records(tiny):
    r = {x["key"]: x for x in compute_records(tiny)["records"]}
    pwh = r["player_week_high"]
    assert pwh["holder"] == "Al" and pwh["user_id"] == "u1"
    assert "QB_B" in pwh["detail"]

    bench = r["bench_week_high"]
    assert bench["value"] == 28.0 and bench["holder"] == "Al"
    assert "RB_B" in bench["detail"]

    # Fixture's player_points ids (P11, P21, ...) have no matching rows in
    # player_weeks, so the season-high player can't be attributed to a
    # manager -- this exercises that fallback rather than crashing.
    season_high = r["player_season_high"]
    assert season_high["value"] == 200.0
    assert season_high["holder"] is None and season_high["user_id"] is None
    assert "P11" in season_high["detail"]


def test_json_serializable_friendly(tiny):
    import json

    out = compute_records(tiny)
    json.dumps(out)  # raises on numpy scalars / non-native types
