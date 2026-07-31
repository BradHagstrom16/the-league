from leaguestats.draftstats import compute_drafts

def test_surplus_and_steals(tiny):
    out = compute_drafts(tiny)
    top = out["steals"][0]
    assert top["player_name"] == "P11" and top["surplus"] == 42.5
    assert all(s["player_name"] != "P31" for s in out["steals"])  # keeper excluded
    # Round 1 avg 157.5; P14 scored 100 -> -57.5, the worst surplus in the
    # fixture (round-1 busts are eligible, not excluded).
    worst = out["busts"][0]
    assert worst["player_name"] == "P14" and worst["surplus"] == -57.5
    # P24 (round 2, 40 - 90 = -50.0) is the next-worst -- confirms the
    # rounds-2+ path is still covered alongside round 1.
    assert out["busts"][1]["player_name"] == "P24" and out["busts"][1]["surplus"] == -50.0

def test_slot_outcomes_and_qb_timing(tiny):
    out = compute_drafts(tiny)
    slot1 = next(r for r in out["slot_outcomes"] if r["slot"] == 1)
    assert slot1["titles"] == 1 and slot1["avg_finish"] == 2.0
    qt = {r["user_id"]: r for r in out["qb_timing"]}
    assert qt["u1"]["first_qb_round"] == 1 and qt["u1"]["finish"] == 2
    # u1's non-keeper picks: P11 (QB), P21 (RB) — P31 is a keeper and excluded
    assert out["tendencies"]["u1"] == {"QB": 0.5, "RB": 0.5}

def test_steals_by_manager(tiny):
    out = compute_drafts(tiny)
    # u1's non-keeper picks are P11 (+42.5 surplus) and P21 (+30) — P31 is a
    # keeper and excluded, so P11 is u1's top steal.
    assert out["steals_by_manager"]["u1"][0]["player_name"] == "P11"
