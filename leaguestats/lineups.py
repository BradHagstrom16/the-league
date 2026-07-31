"""Lineup efficiency & benchings: how many bench points a team left on the
table each week, relative to the best lineup obtainable from its full
rostered player pool that week.

Slot eligibility sets below form a laminar family (each pair is either
nested or disjoint: single-position slots are disjoint from each other,
FLEX's set is a subset of SUPER_FLEX's, and both are disjoint from the
untouched QB/K/DEF singles). That structure is exactly what makes the
most-restrictive-slot-first greedy in `optimal_points` provably optimal —
*given that non-positive-scoring players are excluded first* (an unfilled
slot scores 0, so a player who'd score 0 or less is never worth starting;
dropping them can only free up capacity, never lower the achievable total,
which reduces the problem to the non-negative case the greedy handles
optimally). `tests/test_lineups.py` guards the claim with a DP-based
exhaustive cross-check that includes negative-point inputs.
"""
from __future__ import annotations

import pandas as pd

ELIGIBLE = {
    "QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"},
    "K": {"K"}, "DEF": {"DEF"},
    "FLEX": {"RB", "WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
}


def optimal_points(players: list[tuple[str, float]], slots: list[str]) -> float:
    """Best total points obtainable by assigning `players` (position, points)
    to `slots` (BN/IR already stripped by the caller). Unknown slot names are
    ignored; players whose position is empty/unrecognized are eligible for
    nothing and simply never get picked. Fewer players than slots is legal
    (early-season/short-roster data) — unfillable slots contribute 0.

    Non-positive-scoring players are dropped before the greedy runs: an
    unfilled slot scores 0, so the true maximum never starts a player who'd
    score 0 or less (benching them is always at least as good, and frees the
    slot for someone else). Excluding them first reduces this to the
    non-negative case, which is exactly where most-restrictive-first greedy
    is optimal for this laminar slot family."""
    candidates = [p for p in players if p[1] > 0]
    order = sorted((s for s in slots if s in ELIGIBLE), key=lambda s: len(ELIGIBLE[s]))
    ranked = sorted(range(len(candidates)), key=lambda i: candidates[i][1], reverse=True)
    used = [False] * len(candidates)
    total = 0.0
    for slot in order:
        elig = ELIGIBLE[slot]
        for i in ranked:
            if not used[i] and candidates[i][0] in elig:
                used[i] = True
                total += candidates[i][1]
                break
    return total


def _season_slots(settings: pd.DataFrame, season: int) -> list[str]:
    """Starting slots for a season, BN/IR stripped."""
    row = settings[settings.season.astype(int) == int(season)]
    if not len(row):
        return []
    raw = str(row.iloc[0]["roster_positions"])
    return [s for s in raw.split("|") if s not in ("BN", "IR")]


def _team_weeks(data) -> pd.DataFrame:
    """One row per (season, week, roster_id) that has player_weeks data:
    actual (started sum), optimal (best lineup from the full roster that
    week), and the highest-scoring benched player for that week."""
    pw = data.player_weeks
    pw = pw[pw.is_playoff == 0]
    if pw.empty:
        return pd.DataFrame(columns=["season", "week", "roster_id", "user_id",
                                      "actual", "optimal", "biggest_miss_player",
                                      "biggest_miss_points"])

    slot_cache: dict[int, list[str]] = {}
    rows = []
    for (season, week, roster_id), g in pw.groupby(["season", "week", "roster_id"]):
        season = int(season)
        if season not in slot_cache:
            slot_cache[season] = _season_slots(data.settings, season)
        slots = slot_cache[season]

        points = g.points.fillna(0.0).astype(float)
        positions = g.position.fillna("")
        actual = float(points[g.started == 1].sum())
        optimal = optimal_points(list(zip(positions, points)), slots)

        bench = g.assign(points=points)[g.started == 0]
        if len(bench):
            top = bench.loc[bench.points.idxmax()]
            biggest_miss_player = top.player_name
            biggest_miss_points = float(top.points)
        else:
            biggest_miss_player = None
            biggest_miss_points = 0.0

        rows.append(dict(
            season=season, week=int(week), roster_id=int(roster_id),
            user_id=g.user_id.iloc[0], actual=actual, optimal=optimal,
            biggest_miss_player=biggest_miss_player,
            biggest_miss_points=biggest_miss_points,
        ))
    return pd.DataFrame(rows)


def _summarize(rows: pd.DataFrame, data) -> list[dict]:
    """Aggregate actual/optimal by user_id, adding name/efficiency/bench_left."""
    agg = rows.groupby("user_id")[["actual", "optimal"]].sum().reset_index()
    out = []
    for _, r in agg.iterrows():
        actual, optimal = float(r["actual"]), float(r["optimal"])
        efficiency = round(actual / optimal, 4) if optimal > 0 else 0.0
        out.append(dict(
            user_id=r["user_id"], name=data.display(r["user_id"]),
            actual=round(actual, 2), optimal=round(optimal, 2),
            efficiency=efficiency, bench_left=round(optimal - actual, 2),
        ))
    return out


def compute_lineups(data) -> dict:
    """Regular-season lineup efficiency: per-season and career summaries per
    manager, plus the 15 worst single-week benching decisions all-time."""
    tw = _team_weeks(data)
    if tw.empty:
        return {"seasons": {}, "career": [], "worst_benchings": []}

    matchups = data.reg_matchups()[["season", "week", "roster_id", "result", "opponent_points"]]
    tw = tw.merge(matchups, on=["season", "week", "roster_id"], how="left")

    seasons_out = {}
    for season, g in tw.groupby("season"):
        seasons_out[int(season)] = _summarize(g, data)

    career = _summarize(tw, data)

    tw = tw.assign(delta=tw["optimal"] - tw["actual"])
    tw = tw.assign(would_have_won=(tw["result"] == "L") & (tw["optimal"] > tw["opponent_points"]))
    worst = tw.sort_values("delta", ascending=False).head(15)

    worst_benchings = []
    for _, r in worst.iterrows():
        result = r["result"] if pd.notna(r["result"]) else None
        worst_benchings.append(dict(
            season=int(r["season"]), week=int(r["week"]), user_id=r["user_id"],
            name=data.display(r["user_id"]), actual=round(float(r["actual"]), 2),
            optimal=round(float(r["optimal"]), 2), delta=round(float(r["delta"]), 2),
            result=result, would_have_won=bool(r["would_have_won"]),
            biggest_miss_player=r["biggest_miss_player"],
            biggest_miss_points=round(float(r["biggest_miss_points"]), 2),
        ))

    return {"seasons": seasons_out, "career": career, "worst_benchings": worst_benchings}
