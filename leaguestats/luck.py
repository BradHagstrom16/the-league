"""Luck & schedule stats: all-play record, expected wins, and strength of
schedule, plus the "heists" (cheapest wins) and "robbed" (best losses) leader
boards.

All-play is computed per (season, week) from `reg_matchups()` -- each row
there is one team's perspective of a played regular-season game, and every
user_id appears exactly once per (season, week) group -- then the weekly
(w, l, t) tuples are summed. Doing the comparison at the week level (rather
than pre-aggregating season totals) keeps career numbers era-safe: a 10-team
season and a 12-team season each contribute correctly-sized all-play tuples
per week before they're added together.
"""
from __future__ import annotations

from collections import defaultdict

from leaguestats.loading import LeagueData

_CLOSE_MARGIN = 5
_TOP_N = 10


def allplay_week(scores: dict[str, float]) -> dict[str, tuple[int, int, int]]:
    """For each key, its (w, l, t) record against every other key's score
    that week."""
    result: dict[str, tuple[int, int, int]] = {}
    items = list(scores.items())
    for key, value in items:
        w = l = t = 0
        for other_key, other_value in items:
            if other_key == key:
                continue
            if value > other_value:
                w += 1
            elif value < other_value:
                l += 1
            else:
                t += 1
        result[key] = (w, l, t)
    return result


def _allplay_pct(w: int, l: int, t: int) -> float:
    games = w + l + t
    return (w + 0.5 * t) / games if games else 0.0


def _build_row(data: LeagueData, uid: str, w: int, l: int, t: int, actual_w: int,
               games: int, close_w: int, close_l: int, sos_sum: float,
               sos_count: int) -> dict:
    pct = _allplay_pct(w, l, t)
    exp_wins = pct * games
    sos = sos_sum / sos_count if sos_count else 0.0
    return {
        "user_id": uid,
        "name": data.display(uid),
        "allplay_w": w,
        "allplay_l": l,
        "allplay_t": t,
        "allplay_pct": round(pct, 4),
        "exp_wins": round(exp_wins, 2),
        "actual_wins": actual_w,
        "luck_delta": round(actual_w - exp_wins, 2),
        "close_w": close_w,
        "close_l": close_l,
        "sos": round(sos, 4),
    }


def _leaderboard(rows, n: int, ascending: bool, data: LeagueData) -> list[dict]:
    rows = rows.sort_values("points", ascending=ascending).head(n)
    out = []
    for row in rows.itertuples(index=False):
        out.append({
            "season": int(row.season),
            "week": int(row.week),
            "user_id": row.user_id,
            "name": data.display(row.user_id),
            "points": float(row.points),
            "opp_points": float(row.opponent_points),
            "opp_user_id": row.opponent_user_id,
        })
    return out


def compute_luck(data: LeagueData) -> dict:
    rm = data.reg_matchups()

    # season -> user_id -> [w, l, t], summed from each week's all-play result.
    season_allplay: dict = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    # season -> user_id -> actual-record / close-game / games-played counters.
    season_actual: dict = defaultdict(lambda: defaultdict(
        lambda: {"w": 0, "games": 0, "close_w": 0, "close_l": 0}))

    for (season, _week), grp in rm.groupby(["season", "week"]):
        scores = dict(zip(grp.user_id, grp.points))
        for uid, (w, l, t) in allplay_week(scores).items():
            acc = season_allplay[season][uid]
            acc[0] += w
            acc[1] += l
            acc[2] += t

    for row in rm.itertuples(index=False):
        stats = season_actual[row.season][row.user_id]
        stats["games"] += 1
        margin = abs(row.points - row.opponent_points)
        if row.points > row.opponent_points:
            stats["w"] += 1
            if margin < _CLOSE_MARGIN:
                stats["close_w"] += 1
        elif row.points < row.opponent_points:
            if margin < _CLOSE_MARGIN:
                stats["close_l"] += 1

    # Each season's opponents' season-long all-play pct, used for SOS.
    season_pct = {
        season: {uid: _allplay_pct(*tuple(v)) for uid, v in users.items()}
        for season, users in season_allplay.items()
    }

    # season -> user_id -> [sum of opponent all-play pct, games played].
    season_sos: dict = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    for row in rm.itertuples(index=False):
        term = season_pct[row.season].get(row.opponent_user_id, 0.0)
        acc = season_sos[row.season][row.user_id]
        acc[0] += term
        acc[1] += 1

    seasons_out: dict[int, list[dict]] = {}
    career_allplay: dict = defaultdict(lambda: [0, 0, 0])
    career_actual: dict = defaultdict(lambda: {"w": 0, "games": 0, "close_w": 0, "close_l": 0})
    career_sos: dict = defaultdict(lambda: [0.0, 0])

    for season in sorted(season_allplay.keys()):
        rows = []
        for uid, (w, l, t) in season_allplay[season].items():
            actual = season_actual[season][uid]
            sos_acc = season_sos[season][uid]
            rows.append(_build_row(data, uid, w, l, t, actual["w"], actual["games"],
                                    actual["close_w"], actual["close_l"],
                                    sos_acc[0], sos_acc[1]))

            ca = career_allplay[uid]
            ca[0] += w
            ca[1] += l
            ca[2] += t
            cact = career_actual[uid]
            cact["w"] += actual["w"]
            cact["games"] += actual["games"]
            cact["close_w"] += actual["close_w"]
            cact["close_l"] += actual["close_l"]
            csos = career_sos[uid]
            csos[0] += sos_acc[0]
            csos[1] += sos_acc[1]

        rows.sort(key=lambda r: r["user_id"])
        seasons_out[int(season)] = rows

    career_rows = []
    for uid, (w, l, t) in career_allplay.items():
        cact = career_actual[uid]
        csos = career_sos[uid]
        career_rows.append(_build_row(data, uid, w, l, t, cact["w"], cact["games"],
                                       cact["close_w"], cact["close_l"],
                                       csos[0], csos[1]))
    career_rows.sort(key=lambda r: r["user_id"])

    wins = rm[rm.points > rm.opponent_points]
    losses = rm[rm.points < rm.opponent_points]
    heists = _leaderboard(wins, _TOP_N, ascending=True, data=data)
    robbed = _leaderboard(losses, _TOP_N, ascending=False, data=data)

    return {"seasons": seasons_out, "career": career_rows, "heists": heists, "robbed": robbed}
