import pandas as pd
from leaguestats.txstats import compute_transactions

def _with_post_rows(tiny):
    tiny.player_weeks = pd.concat([tiny.player_weeks, pd.DataFrame([
        # WAIV_1 started by roster 2 after the week-2 pickup
        dict(season=2024, week=3, roster_id=2, user_id="u2", player_id="WAIV_1",
             player_name="WAIV_1", position="RB", points=35.0, started=1, is_playoff=0),
        # traded players' post-trade production (trade was week 2)
        dict(season=2024, week=3, roster_id=3, user_id="u3", player_id="RB_A",
             player_name="RB_A", position="RB", points=12.0, started=1, is_playoff=0),
        dict(season=2024, week=3, roster_id=1, user_id="u1", player_id="WR_C",
             player_name="WR_C", position="WR", points=22.0, started=1, is_playoff=0),
    ])], ignore_index=True)
    return tiny

def test_faab(tiny):
    out = compute_transactions(_with_post_rows(tiny))
    faab = {r["user_id"]: r for r in out["faab_seasons"][2024]}
    assert faab["u2"]["spent"] == 30 and faab["u2"]["points_after"] == 35.0
    assert faab["u2"]["ppd"] == 1.17
    assert "u4" not in faab            # failed claim ignored
    assert out["best_buys"][0]["player_name"] == "WAIV_1"

def test_trade_ledger(tiny):
    out = compute_transactions(_with_post_rows(tiny))
    t = out["trades"][0]
    sides = {s["user_id"]: s for s in t["sides"]}
    assert sides["u1"]["players_gained"] == ["WR_C"]
    assert sides["u1"]["points_after"] == 22.0 and sides["u3"]["points_after"] == 12.0
    assert t["winner_user_id"] == "u1" and t["margin"] == 10.0
