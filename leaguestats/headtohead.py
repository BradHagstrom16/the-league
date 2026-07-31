"""Head-to-head history between every pair of managers who have ever met,
across ALL matchups (regular season + playoffs) and all seasons.

Unlike the other stats modules, H2H needs `user_id`/`opponent_user_id` merged
onto the *full* matchups table (no playoff filter), so `with_users` here is
the un-filtered twin of `LeagueData.reg_matchups()`. It's kept local to this
module per the task brief; a later pass may hoist it onto `LeagueData` if
other modules end up needing the same unfiltered merge.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from leaguestats.loading import LeagueData


def with_users(matchups: pd.DataFrame, managers: pd.DataFrame) -> pd.DataFrame:
    """All matchup rows (regular + playoff), numeric season/week/points/roster
    ids, boolean `is_playoff`, plus `user_id`/`opponent_user_id` merged on
    from `managers` (roster ids are only unique within a season)."""
    m = matchups.copy()
    for c in ("season", "week", "roster_id", "opponent_roster_id"):
        m[c] = m[c].astype(int)
    for c in ("points", "opponent_points"):
        m[c] = m[c].astype(float)
    if m.is_playoff.dtype == object:
        m["is_playoff"] = m.is_playoff.astype(str).eq("True")
    else:
        m["is_playoff"] = m.is_playoff.astype(bool)

    u = managers[["season", "roster_id", "user_id"]].copy()
    u["season"] = u.season.astype(int)
    u["roster_id"] = u.roster_id.astype(int)
    m = m.merge(u, on=["season", "roster_id"], how="left")
    m = m.merge(u.rename(columns={"roster_id": "opponent_roster_id",
                                  "user_id": "opponent_user_id"}),
                on=["season", "opponent_roster_id"], how="left")
    return m


def _streak(results: list[str]) -> str:
    """`results` is a chronological list of single-letter outcomes ('W'/'L'/'T')
    from one side's perspective. Returns e.g. "W2" for the last 2 meetings
    both being wins, walking back from the most recent result."""
    last = results[-1]
    count = 0
    for r in reversed(results):
        if r != last:
            break
        count += 1
    return f"{last}{count}"


_FLIP = {"W": "L", "L": "W", "T": "T"}


def _meetings(data: LeagueData) -> dict[str, list[dict]]:
    """user-pair key "a|b" (a, b sorted user ids) -> chronological list of
    meetings, each `{season, week, is_playoff, a_points, b_points,
    winner_user}` from a's perspective (a is the first id in the sorted key)."""
    m = with_users(data.matchups, data.managers)
    m = m.dropna(subset=["user_id", "opponent_user_id"])
    # Each game produces two mirrored rows (one per team's perspective);
    # keep exactly one per game.
    m = m[m.roster_id < m.opponent_roster_id].sort_values(["season", "week"])

    pairs: dict[str, list[dict]] = defaultdict(list)
    for row in m.itertuples(index=False):
        a, b = sorted((row.user_id, row.opponent_user_id))
        if row.user_id == a:
            a_points, b_points = row.points, row.opponent_points
        else:
            a_points, b_points = row.opponent_points, row.points

        if a_points > b_points:
            winner_user = a
        elif b_points > a_points:
            winner_user = b
        else:
            winner_user = None

        pairs[f"{a}|{b}"].append({
            "season": int(row.season),
            "week": int(row.week),
            "is_playoff": bool(row.is_playoff),
            "a_points": float(a_points),
            "b_points": float(b_points),
            "winner_user": winner_user,
        })
    return pairs


def compute_h2h(data: LeagueData) -> dict:
    pairs = _meetings(data)

    grid: dict[str, dict[str, dict]] = defaultdict(dict)
    reg_playoff_split: dict[str, dict] = {}
    game_counts: dict[str, int] = defaultdict(int)

    for key, meetings in pairs.items():
        a, b = key.split("|")
        game_counts[a] += len(meetings)
        game_counts[b] += len(meetings)

        results_a = ["T" if m["winner_user"] is None
                     else ("W" if m["winner_user"] == a else "L")
                     for m in meetings]
        results_b = [_FLIP[r] for r in results_a]

        w = results_a.count("W")
        l = results_a.count("L")
        t = results_a.count("T")

        margin_sum = sum(m["a_points"] - m["b_points"] for m in meetings)
        avg_margin_a = margin_sum / len(meetings)
        avg_margin_b = -avg_margin_a

        grid[a][b] = {
            "w": w, "l": l, "t": t,
            "avg_margin": round(avg_margin_a, 2),
            "streak": _streak(results_a),
        }
        grid[b][a] = {
            "w": l, "l": w, "t": t,
            "avg_margin": round(avg_margin_b, 2),
            "streak": _streak(results_b),
        }

        reg = [0, 0, 0]
        playoff = [0, 0, 0]
        for m, r in zip(meetings, results_a):
            bucket = playoff if m["is_playoff"] else reg
            bucket["WLT".index(r)] += 1
        reg_playoff_split[key] = {"reg": reg, "playoff": playoff}

    all_ids = set(game_counts)
    users = sorted(all_ids, key=lambda uid: (-game_counts[uid], uid))
    users_out = [{"user_id": uid, "name": data.display(uid)} for uid in users]

    return {
        "users": users_out,
        "grid": {a: dict(opponents) for a, opponents in grid.items()},
        "pairs": dict(pairs),
        "reg_playoff_split": reg_playoff_split,
    }
