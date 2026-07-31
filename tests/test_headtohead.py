from leaguestats.headtohead import compute_h2h

def test_grid_symmetric_and_correct(tiny):
    out = compute_h2h(tiny)
    a = out["grid"]["u1"]["u3"]
    assert (a["w"], a["l"]) == (1, 1) and a["avg_margin"] == -2.5
    b = out["grid"]["u3"]["u1"]
    assert (b["w"], b["l"]) == (1, 1) and b["avg_margin"] == 2.5
    assert out["grid"]["u1"]["u2"] == {"w": 1, "l": 0, "t": 0,
                                       "avg_margin": 10.0, "streak": "W1"}

def test_pair_log_and_split(tiny):
    out = compute_h2h(tiny)
    key = "u1|u3"
    assert len(out["pairs"][key]) == 2
    assert out["reg_playoff_split"][key] == {"reg": [0, 1, 0], "playoff": [1, 0, 0]}
    assert out["grid"]["u1"]["u3"]["streak"] == "W1"
