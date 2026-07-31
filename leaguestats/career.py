"""Career / franchise-history aggregates.

Bundles each manager's stats across every season they've played (record,
points, titles, streaks, ...) plus a per-season recap (champion, last place).

`longest_run` is a small pure helper factored out because it's also useful
to (and imported by) other modules that need "longest streak of a repeated
outcome" logic, e.g. weekly/matchup-level stats.
"""
from __future__ import annotations

import pandas as pd

from leaguestats.loading import LeagueData


def longest_run(results: list[str], target: str) -> int:
    """Longest run of consecutive elements in `results` equal to `target`."""
    best = cur = 0
    for r in results:
        if r == target:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def _played_standings(data: LeagueData) -> pd.DataFrame:
    """Standings rows for seasons that have actually concluded (non-null
    `finish`) -- excludes an in-progress season (e.g. 2026 with NaN finish),
    with the relevant columns coerced to plain numeric types."""
    s = data.standings
    s = s[s.finish.notna()].copy()
    s["season"] = s.season.astype(int)
    s["finish"] = s.finish.astype(int)
    for col in ("wins", "losses", "ties", "champion", "made_playoffs"):
        s[col] = s[col].fillna(0).astype(int)
    for col in ("points_for", "points_against"):
        s[col] = s[col].astype(float)
    return s


def _streaks(data: LeagueData) -> dict[str, tuple[int, int]]:
    """user_id -> (longest_win_streak, longest_loss_streak) across regular
    season games, games ordered by season then week."""
    m = data.reg_matchups()
    m = m.dropna(subset=["user_id"]).sort_values(["user_id", "season", "week"])
    out: dict[str, tuple[int, int]] = {}
    for uid, grp in m.groupby("user_id")["result"]:
        results = list(grp)
        out[uid] = (longest_run(results, "W"), longest_run(results, "L"))
    return out


def _active_ids(data: LeagueData) -> set[str]:
    newest = data.settings.season.astype(int).max()
    mgrs = data.managers[data.managers.season.astype(int) == newest]
    return set(mgrs.user_id)


def toilet_bowl_loser(data: LeagueData, season: int) -> str | None:
    """user_id of the season's toilet-bowl loser, or None without a bracket.

    In this league the punishment goes to the WINNER of the losers-bracket
    position-1 game (you win your way into the punishment) — commissioner-
    confirmed and verified against all five played seasons.
    """
    br = data.brackets
    g = br[(br.season.astype(int) == int(season)) & (br.bracket == "losers")]
    g = g[(g.position.astype("float") == 1) & g.winner.notna()]
    if not len(g):
        return None
    rid = int(float(g.iloc[0].winner))
    return data.r2u(int(season)).get(rid)


def compute_career(data: LeagueData) -> dict:
    s = _played_standings(data)
    # Last place = the toilet-bowl loser where a losers bracket exists;
    # worst regular-season record only as a fallback.
    tb_by_season = {int(season): toilet_bowl_loser(data, int(season))
                    for season in s.season.unique()}
    s["season_worst"] = s.groupby("season")["finish"].transform("max")
    s["is_last"] = s.apply(
        lambda r: int(str(r.user_id) == tb_by_season[int(r.season)])
        if tb_by_season[int(r.season)]
        else int(r.finish == r.season_worst), axis=1)

    agg = s.groupby("user_id").agg(
        seasons=("season", "nunique"),
        wins=("wins", "sum"),
        losses=("losses", "sum"),
        ties=("ties", "sum"),
        pf=("points_for", "sum"),
        pa=("points_against", "sum"),
        avg_finish=("finish", "mean"),
        titles=("champion", "sum"),
        playoff_apps=("made_playoffs", "sum"),
        last_places=("is_last", "sum"),
    ).reset_index()

    streaks = _streaks(data)
    active_ids = _active_ids(data)

    managers = []
    for row in agg.itertuples(index=False):
        uid = row.user_id
        games = row.wins + row.losses + row.ties
        win_pct = round(row.wins / games, 4) if games else 0.0
        win_streak, loss_streak = streaks.get(uid, (0, 0))
        managers.append({
            "user_id": str(uid),
            "name": data.display(uid),
            "handle": data.handles.get(uid, str(uid)),
            "avatar": data.avatars.get(uid, ""),
            "seasons": int(row.seasons),
            "wins": int(row.wins),
            "losses": int(row.losses),
            "ties": int(row.ties),
            "win_pct": float(win_pct),
            "pf": round(float(row.pf), 2),
            "pa": round(float(row.pa), 2),
            "avg_finish": round(float(row.avg_finish), 2),
            "titles": int(row.titles),
            "playoff_apps": int(row.playoff_apps),
            "last_places": int(row.last_places),
            "longest_win_streak": int(win_streak),
            "longest_loss_streak": int(loss_streak),
            "active": bool(uid in active_ids),
        })
    managers.sort(key=lambda m: m["win_pct"], reverse=True)

    finish_by_year: dict[str, dict[int, int]] = {}
    for row in s.itertuples(index=False):
        finish_by_year.setdefault(str(row.user_id), {})[int(row.season)] = int(row.finish)

    seasons = []
    for season, grp in s.groupby("season"):
        champs = grp[grp.champion == 1]
        champion_user = str(champs.iloc[0].user_id) if len(champs) else None
        last_user = tb_by_season.get(int(season)) or str(
            grp[grp.finish == grp.finish.max()].iloc[0].user_id)
        seasons.append({
            "season": int(season),
            "era": data.era(int(season)),
            "champion_user": champion_user,
            "champion_name": data.display(champion_user) if champion_user else None,
            "last_user": last_user,
            "last_name": data.display(last_user),
        })
    seasons.sort(key=lambda x: x["season"])

    return {"managers": managers, "finish_by_year": finish_by_year, "seasons": seasons}
