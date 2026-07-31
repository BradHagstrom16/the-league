from leaguestats.career import compute_career

def test_career_basics(tiny):
    out = compute_career(tiny)
    by = {m["user_id"]: m for m in out["managers"]}
    assert by["u1"]["wins"] == 2 and by["u1"]["losses"] == 1
    assert by["u1"]["titles"] == 1 and by["u1"]["name"] == "Al"
    assert by["u1"]["pf"] == 345.0 and by["u1"]["avg_finish"] == 2.0
    assert by["u4"]["last_places"] == 1 and by["u4"]["playoff_apps"] == 0

def test_streaks(tiny):
    out = compute_career(tiny)
    by = {m["user_id"]: m for m in out["managers"]}
    assert by["u3"]["longest_win_streak"] == 3   # W W W
    assert by["u1"]["longest_win_streak"] == 1   # W L W
    assert by["u4"]["longest_loss_streak"] == 3

def test_finish_by_year_and_seasons(tiny):
    out = compute_career(tiny)
    assert out["finish_by_year"]["u3"][2024] == 1
    s = out["seasons"][0]
    assert s["champion_user"] == "u1" and s["last_user"] == "u4"
