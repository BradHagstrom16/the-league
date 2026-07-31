import pandas as pd
import pytest
from leaguestats.keepers import (
    left_roster, audit_keepers, compute_keepers, KEEPER_MIN_ROUND, MAX_KEEPERS,
)

def _mini(tiny):
    """Graft a 2023 season onto the tiny fixture to exercise the audit."""
    d23 = pd.DataFrame([
        # u1 drafts KX rd 7 and keeps him honestly at rd 7 in 2024
        dict(season=2023, round=7, overall_pick=25, draft_slot=1,
             slot_owner_roster_id=1, roster_id=1, traded_pick=0, user_id="u1",
             manager="h1", player_id="KX", player_name="KX", position="WR",
             is_keeper=False),
        # u2 drafts KY rd 6, drops him mid-season, keeps him at rd 5 (correct: 6-1)
        dict(season=2023, round=6, overall_pick=22, draft_slot=2,
             slot_owner_roster_id=2, roster_id=2, traded_pick=0, user_id="u2",
             manager="h2", player_id="KY", player_name="KY", position="RB",
             is_keeper=False),
        # u3 drafts KZ rd 3 — round-ineligible to keep
        dict(season=2023, round=3, overall_pick=9, draft_slot=3,
             slot_owner_roster_id=3, roster_id=3, traded_pick=0, user_id="u3",
             manager="h3", player_id="KZ", player_name="KZ", position="WR",
             is_keeper=False),
    ])
    k24 = pd.DataFrame([
        dict(season=2024, round=7, overall_pick=25, draft_slot=1,
             slot_owner_roster_id=1, roster_id=1, traded_pick=0, user_id="u1",
             manager="h1", player_id="KX", player_name="KX", position="WR",
             is_keeper=True),
        dict(season=2024, round=6, overall_pick=21, draft_slot=2,   # kept at drafted round: correct (no left-roster penalty in this league)
             slot_owner_roster_id=2, roster_id=2, traded_pick=0, user_id="u2",
             manager="h2", player_id="KY", player_name="KY", position="RB",
             is_keeper=True),
        dict(season=2024, round=3, overall_pick=9, draft_slot=3,
             slot_owner_roster_id=3, roster_id=3, traded_pick=0, user_id="u3",
             manager="h3", player_id="KZ", player_name="KZ", position="WR",
             is_keeper=True),
    ])
    tiny.drafts = pd.concat([tiny.drafts, d23, k24], ignore_index=True)
    tiny.transactions = pd.concat([tiny.transactions, pd.DataFrame([
        dict(season=2023, transaction_id="t9", week=6, type="free_agent",
             status="complete", created_ms=5000, created_date="2023-10-15",
             roster_id=2, manager="h2", action="drop", player_id="KY",
             player_name="KY", position="RB", faab_bid=""),
    ])], ignore_index=True)
    m23 = tiny.managers.assign(season=2023)
    tiny.managers = pd.concat([tiny.managers, m23], ignore_index=True)
    s23 = tiny.settings.iloc[[0]].assign(season=2023, draft_start_ms=100)
    tiny.settings = pd.concat([tiny.settings, s23], ignore_index=True)
    return tiny

def test_left_roster(tiny):
    d = _mini(tiny)
    assert left_roster(d, 2023, "KY", "u2") is True    # dropped mid-season
    assert left_roster(d, 2023, "KX", "u1") is False   # stayed all year

def test_audit(tiny):
    d = _mini(tiny)
    rows = {r["player_id"]: r for r in audit_keepers(d)}
    assert rows["KX"]["charged_ok"] and rows["KX"]["need"] == 7
    assert rows["KY"]["charged_ok"] and rows["KY"]["need"] == 6   # left roster, but no penalty exists
    assert not rows["KZ"]["eligible_round"]
    assert not rows["KX"]["repeat_keep"]


def test_constants():
    assert KEEPER_MIN_ROUND == 6
    assert MAX_KEEPERS == 2


def test_compute_keepers_structure(tiny):
    d = _mini(tiny)
    out = compute_keepers(d)

    assert out["rules"] == [
        "A manager may keep 2 players maximum.",
        "The player must have been drafted in the previous year's draft in "
        "round 6 or later. A player may not be kept two years in a row.",
        "You keep a player at the round you drafted him.",
        "Draft pick trading is allowed before and during the draft, "
        "including keepers. Future years' picks cannot be traded.",
    ]

    # 3 audit-graded keepers (KX, KY, KZ); P31 (the original tiny keeper) has
    # no 2023 draft record so it's ungraded and excluded from audit/summary.
    summary = out["summary"]
    assert summary["n"] == 3
    assert summary["charged_ok"] == 3          # KX, KY, KZ all charged their drafted round
    assert summary["rule_flags"]["ineligible_round"] == 1   # KZ (round 3)
    assert summary["rule_flags"]["repeat_keep"] == 0
    assert summary["rule_flags"]["wrong_round_charge"] == 0
    assert summary["rule_flags"]["max_keepers_exceeded"] == 0

    # value/by_manager cover every is_keeper pick in a played season,
    # including P31 (ungraded for audit, but still a keeper for value).
    by_player = {r["player_name"]: r for r in out["value"]}
    assert set(by_player) == {"P31", "KX", "KY", "KZ"}
    assert all({"season", "user_id", "name", "player_name", "keep_round",
                "points", "surplus"} <= set(r) for r in out["value"])
    assert by_player["P31"]["surplus"] > 0     # 80 pts vs a low round-3 mean
    assert by_player["KZ"]["surplus"] < 0      # 0 pts vs a positive round-3 mean

    mgr_rows = {r["user_id"]: r for r in out["by_manager"]}
    assert mgr_rows["u1"]["keeps"] == 2        # P31 + KX
    assert mgr_rows["u2"]["keeps"] == 1
    assert mgr_rows["u3"]["keeps"] == 1

    # No pre_draft season in this fixture -> nothing declared yet.
    assert out["declared_next"] == []


def test_declared_next(tiny):
    d = _mini(tiny)
    # Graft a pre_draft 2025 season carrying one already-declared keeper.
    d25 = pd.DataFrame([
        dict(season=2025, round=8, overall_pick=29, draft_slot=1,
             slot_owner_roster_id=1, roster_id=1, traded_pick=0, user_id="u1",
             manager="h1", player_id="KX", player_name="KX", position="WR",
             is_keeper=True),
    ])
    d.drafts = pd.concat([d.drafts, d25], ignore_index=True)
    s25 = d.settings.iloc[[0]].assign(season=2025, status="pre_draft")
    d.settings = pd.concat([d.settings, s25], ignore_index=True)

    out = compute_keepers(d)
    assert out["declared_next"] == [
        {"user_id": "u1", "name": "Al", "player_name": "KX", "round": 8},
    ]

    # The 2025 KX pick has a valid prior-season (2024, round 7) draft record
    # -- it *could* be graded -- but 2025 is pre_draft (not yet played), so
    # it must surface ONLY via declared_next, never via audit/summary.
    assert all(r["season"] != 2025 for r in out["audit"])
    assert out["summary"]["n"] == 3            # unchanged from test_compute_keepers_structure
    assert out["summary"]["charged_ok"] == 3   # unchanged from test_compute_keepers_structure
