import pandas as pd
import pytest
from leaguestats.loading import LeagueData

# Weekly team scores (weeks 1-3 regular, week 4 playoff final: r1 vs r2).
# w1: r1 110 beats r2 100; r3 90 beats r4 80
# w2: r1 105 loses to r3 120; r2 95 beats r4 85
# w3: r1 130 beats r4 70;  r2 100 loses to r3 101
# Regular season: r3 3-0, r1 2-1, r2 1-2, r4 0-3
# w4 playoff: r1 100 beats r3 90  -> champion u1
_SCHED = [
    (1, 1, 110, 2, 100, False), (1, 3, 90, 4, 80, False),
    (2, 1, 105, 3, 120, False), (2, 2, 95, 4, 85, False),
    (3, 1, 130, 4, 70, False), (3, 2, 100, 3, 101, False),
    (4, 1, 100, 3, 90, True),
]

def _matchups():
    rows = []
    for wk, ra, pa, rb, pb, po in _SCHED:
        for (r1, p1, r2, p2) in ((ra, pa, rb, pb), (rb, pb, ra, pa)):
            rows.append(dict(season=2024, week=wk, roster_id=r1, points=p1,
                             opponent_roster_id=r2, opponent_points=p2,
                             result="W" if p1 > p2 else "L", is_playoff=po,
                             manager=f"h{r1}", team_name=f"T{r1}",
                             opponent_manager=f"h{r2}"))
    return pd.DataFrame(rows)

@pytest.fixture
def tiny() -> LeagueData:
    managers = pd.DataFrame([
        dict(season=2024, league_id="L1", roster_id=r, user_id=f"u{r}",
             manager=f"h{r}", team_name=f"T{r}") for r in (1, 2, 3, 4)])
    standings = pd.DataFrame([
        dict(season=2024, roster_id=3, user_id="u3", manager="h3", wins=3, losses=0,
             ties=0, points_for=311.0, points_against=285.0, finish=1, champion=0,
             made_playoffs=1, draft_slot=3, waiver_budget_used=50, total_moves=5),
        dict(season=2024, roster_id=1, user_id="u1", manager="h1", wins=2, losses=1,
             ties=0, points_for=345.0, points_against=290.0, finish=2, champion=1,
             made_playoffs=1, draft_slot=1, waiver_budget_used=100, total_moves=9),
        dict(season=2024, roster_id=2, user_id="u2", manager="h2", wins=1, losses=2,
             ties=0, points_for=295.0, points_against=296.0, finish=3, champion=0,
             made_playoffs=0, draft_slot=2, waiver_budget_used=0, total_moves=1),
        dict(season=2024, roster_id=4, user_id="u4", manager="h4", wins=0, losses=3,
             ties=0, points_for=235.0, points_against=315.0, finish=4, champion=0,
             made_playoffs=0, draft_slot=4, waiver_budget_used=125, total_moves=3),
    ])
    # Draft: 3 rounds, 4 slots, snake irrelevant here. One keeper (u1 keeps QB_A at rd 3).
    drafts = pd.DataFrame([
        dict(season=2024, round=rd, overall_pick=(rd - 1) * 4 + s, draft_slot=s,
             slot_owner_roster_id=s, roster_id=s, traded_pick=0, user_id=f"u{s}",
             manager=f"h{s}", player_id=f"P{rd}{s}", player_name=f"P{rd}{s}",
             position=pos, is_keeper=(rd == 3 and s == 1))
        for rd, pos in ((1, "QB"), (2, "RB"), (3, "WR"))
        for s in (1, 2, 3, 4)])
    # Player weeks: only roster 1 detailed (enough for lineup tests); others empty.
    player_weeks = pd.DataFrame([
        # week 1, roster 1: starters QB 30, RB 20, WR(FLEX) 25, QB2(SF) 35 = 110
        dict(season=2024, week=1, roster_id=1, user_id="u1", player_id="QB_A",
             player_name="QB_A", position="QB", points=30.0, started=1, is_playoff=0),
        dict(season=2024, week=1, roster_id=1, user_id="u1", player_id="RB_A",
             player_name="RB_A", position="RB", points=20.0, started=1, is_playoff=0),
        dict(season=2024, week=1, roster_id=1, user_id="u1", player_id="WR_A",
             player_name="WR_A", position="WR", points=25.0, started=1, is_playoff=0),
        dict(season=2024, week=1, roster_id=1, user_id="u1", player_id="QB_B",
             player_name="QB_B", position="QB", points=35.0, started=1, is_playoff=0),
        # bench: RB_B 28 (should have started over RB_A -> optimal 118)
        dict(season=2024, week=1, roster_id=1, user_id="u1", player_id="RB_B",
             player_name="RB_B", position="RB", points=28.0, started=0, is_playoff=0),
        dict(season=2024, week=1, roster_id=1, user_id="u1", player_id="WR_B",
             player_name="WR_B", position="WR", points=10.0, started=0, is_playoff=0),
    ])
    transactions = pd.DataFrame([
        # completed FAAB add: u2 buys WAIV_1 for $30 in week 2
        dict(season=2024, transaction_id="t1", week=2, type="waiver", status="complete",
             created_ms=1000, created_date="2024-09-18", roster_id=2, manager="h2",
             action="add", player_id="WAIV_1", player_name="WAIV_1", position="RB",
             faab_bid=30),
        # failed claim on the same player by u4 (must be ignored everywhere)
        dict(season=2024, transaction_id="t2", week=2, type="waiver", status="failed",
             created_ms=1000, created_date="2024-09-18", roster_id=4, manager="h4",
             action="add", player_id="WAIV_1", player_name="WAIV_1", position="RB",
             faab_bid=45),
        # trade t3 week 2: u1 sends RB_A to u3 for WR_C
        dict(season=2024, transaction_id="t3", week=2, type="trade", status="complete",
             created_ms=2000, created_date="2024-09-19", roster_id=3, manager="h3",
             action="add", player_id="RB_A", player_name="RB_A", position="RB", faab_bid=""),
        dict(season=2024, transaction_id="t3", week=2, type="trade", status="complete",
             created_ms=2000, created_date="2024-09-19", roster_id=1, manager="h1",
             action="add", player_id="WR_C", player_name="WR_C", position="WR", faab_bid=""),
        dict(season=2024, transaction_id="t3", week=2, type="trade", status="complete",
             created_ms=2000, created_date="2024-09-19", roster_id=1, manager="h1",
             action="drop", player_id="RB_A", player_name="RB_A", position="RB", faab_bid=""),
        dict(season=2024, transaction_id="t3", week=2, type="trade", status="complete",
             created_ms=2000, created_date="2024-09-19", roster_id=3, manager="h3",
             action="drop", player_id="WR_C", player_name="WR_C", position="WR", faab_bid=""),
    ])
    settings = pd.DataFrame([dict(
        season=2024, league_id="L1", name="Tiny", status="complete", teams=4,
        draft_id="D1", previous_league_id="", max_keepers=2, playoff_teams=2,
        playoff_week_start=4, draft_start_ms=100, draft_date="2024-08-25",
        waiver_budget=125, trade_deadline=13, playoff_seed_type=0,
        roster_positions="QB|RB|FLEX|SUPER_FLEX|BN|BN")])
    brackets = pd.DataFrame([dict(season=2024, bracket="winners", round=1, matchup_id=1,
                                  roster_id_1=1, roster_id_2=3, winner=1, loser=3,
                                  position=1)])
    # Season totals per drafted player. Round averages: r1 157.5, r2 90, r3 45.
    _pts = {"P11": 200, "P12": 180, "P13": 150, "P14": 100,
            "P21": 120, "P22": 110, "P23": 90, "P24": 40,
            "P31": 80, "P32": 30, "P33": 60, "P34": 10}
    player_points = pd.DataFrame([
        dict(season=2024, player_id=pid, player_name=pid,
             position={"1": "QB", "2": "RB", "3": "WR"}[pid[1]],
             weeks_rostered=14, points_regular=float(v), points_total=float(v) + 5,
             points_started=float(v), weeks_started=13)
        for pid, v in _pts.items()])
    return LeagueData(
        matchups=_matchups(), drafts=drafts, standings=standings,
        player_weeks=player_weeks, player_points=player_points,
        transactions=transactions, settings=settings,
        managers=managers, brackets=brackets,
        names={"u1": "Al", "u2": "Bo", "u3": "Cy", "u4": "Di"},
        handles={f"u{r}": f"h{r}" for r in (1, 2, 3, 4)},
        avatars={}, lore={"trophy_name": "The Tiny Cup",
                          "punishments": {2024: "Di waxed his legs"}})
