from leaguestats.luck import allplay_week, compute_luck

def test_allplay_week_pure():
    r = allplay_week({"a": 110.0, "b": 100.0, "c": 90.0, "d": 80.0})
    assert r["a"] == (3, 0, 0) and r["c"] == (1, 2, 0)
    t = allplay_week({"a": 100.0, "b": 100.0, "c": 50.0})
    assert t["a"] == (1, 0, 1) and t["c"] == (0, 2, 0)

def test_season_luck(tiny):
    out = compute_luck(tiny)
    row = {r["user_id"]: r for r in out["seasons"][2024]}
    assert (row["u1"]["allplay_w"], row["u1"]["allplay_l"]) == (8, 1)
    assert row["u1"]["exp_wins"] == 2.67 and row["u1"]["luck_delta"] == -0.67
    assert row["u3"]["luck_delta"] == 1.0
    assert (row["u3"]["close_w"], row["u2"]["close_l"]) == (1, 1)
    # u1 faced u2, u3, u4 whose all-play pcts are 4/9, 6/9, 0/9 -> mean 10/27
    assert row["u1"]["sos"] == 0.3704

def test_heists_and_robbed(tiny):
    out = compute_luck(tiny)
    assert out["heists"][0]["points"] == 90.0 and out["heists"][0]["user_id"] == "u3"
    assert out["robbed"][0]["points"] == 105.0 and out["robbed"][0]["user_id"] == "u1"
