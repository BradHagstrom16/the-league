"""League record book: single best/worst-ever entries across a handful of
categories (highest/lowest scores, biggest margins, longest streaks, best
individual player performances).

Regular-season entries are sourced from `LeagueData.reg_matchups()` (already
numeric/boolean-normalized and merged with `user_id`/`opponent_user_id`).
Playoff entries need the same shape but with the playoff rows *kept* instead
of filtered out, so `_playoff_matchups` below is the playoff-keeping twin of
`reg_matchups()` -- mirrors the pattern `headtohead.with_users` already uses
for the same reason, kept local to this module per the task brief.

Margins (`blowout`/`nailbiter`) are computed on deduped matchup rows
(`roster_id < opponent_roster_id`, i.e. one row per game rather than one per
team) and attributed to the winner. Streak records reuse `longest_run` from
`career` for the actual longest-streak value; `_streak_span` here only
*locates* a run of that already-known length so the record can name the
weeks it happened, it doesn't recompute "longest".
"""
from __future__ import annotations

import pandas as pd

from leaguestats.career import longest_run
from leaguestats.loading import LeagueData


def _r2(value) -> float:
    return round(float(value), 2)


def _record(key: str, label: str, value, holder, user_id, detail: str) -> dict:
    return {"key": key, "label": label, "value": value, "holder": holder,
            "user_id": user_id, "detail": detail}


def _week_detail(season, week, opponent_name: str | None = None) -> str:
    base = f"Week {int(week)}, {int(season)}"
    return f"{base} vs {opponent_name}" if opponent_name else base


def _playoff_matchups(data: LeagueData) -> pd.DataFrame:
    """All matchup rows restricted to playoff games, with numeric season/week
    /roster ids, float points, boolean `is_playoff`, and `user_id`/
    `opponent_user_id` merged on from `managers` -- the playoff-keeping twin
    of `LeagueData.reg_matchups()` (which filters playoff rows *out*)."""
    m = data.matchups.copy()
    for c in ("season", "week", "roster_id", "opponent_roster_id"):
        m[c] = m[c].astype(int)
    for c in ("points", "opponent_points"):
        m[c] = m[c].astype(float)
    if m["is_playoff"].dtype == object:
        m["is_playoff"] = m["is_playoff"].astype(str).eq("True")
    else:
        m["is_playoff"] = m["is_playoff"].astype(bool)
    m = m[m.is_playoff]

    u = data.managers[["season", "roster_id", "user_id"]].copy()
    u["season"] = u.season.astype(int)
    u["roster_id"] = u.roster_id.astype(int)
    m = m.merge(u, on=["season", "roster_id"], how="left")
    m = m.merge(u.rename(columns={"roster_id": "opponent_roster_id",
                                  "user_id": "opponent_user_id"}),
                on=["season", "opponent_roster_id"], how="left")
    return m


def _team_week_extreme(m: pd.DataFrame, data: LeagueData, key: str, label: str,
                        want_max: bool) -> dict:
    """A single team's best/worst single-week score from matchup rows `m`
    (one row per team per week -- not deduped)."""
    idx = m["points"].idxmax() if want_max else m["points"].idxmin()
    row = m.loc[idx]
    uid = row["user_id"]
    opp_name = data.display(row["opponent_user_id"]) if pd.notna(row["opponent_user_id"]) else None
    detail = _week_detail(row["season"], row["week"], opp_name)
    return _record(key, label, _r2(row["points"]), data.display(uid), uid, detail)


def _margin_rows(m: pd.DataFrame) -> pd.DataFrame:
    """One row per game (dedup via `roster_id < opponent_roster_id`), with
    `margin` (nonnegative), `winner_uid`/`winner_name`, and `loser_uid`."""
    d = m[m.roster_id < m.opponent_roster_id].copy()
    d["margin"] = (d["points"] - d["opponent_points"]).abs()
    row_wins = d["points"] > d["opponent_points"]
    d["winner_uid"] = d["user_id"].where(row_wins, d["opponent_user_id"])
    d["loser_uid"] = d["opponent_user_id"].where(row_wins, d["user_id"])
    return d


def _margin_extreme(d: pd.DataFrame, data: LeagueData, key: str, label: str,
                     want_max: bool) -> dict:
    idx = d["margin"].idxmax() if want_max else d["margin"].idxmin()
    row = d.loc[idx]
    loser_name = data.display(row["loser_uid"]) if pd.notna(row["loser_uid"]) else None
    detail = _week_detail(row["season"], row["week"], loser_name)
    return _record(key, label, _r2(row["margin"]), data.display(row["winner_uid"]),
                    row["winner_uid"], detail)


def _played_standings(data: LeagueData) -> pd.DataFrame:
    """Standings rows for concluded seasons only (non-null `finish`), with
    the relevant columns coerced to plain numeric types."""
    s = data.standings
    s = s[s.finish.notna()].copy()
    s["season"] = s.season.astype(int)
    for col in ("points_for", "points_against"):
        s[col] = s[col].astype(float)
    return s


def _season_extreme(s: pd.DataFrame, data: LeagueData, key: str, label: str,
                     column: str, want_max: bool) -> dict:
    idx = s[column].idxmax() if want_max else s[column].idxmin()
    row = s.loc[idx]
    uid = row["user_id"]
    detail = f"{int(row['season'])} season"
    return _record(key, label, _r2(row[column]), data.display(uid), uid, detail)


def _streak_span(results: list[str], weeks: list[tuple[int, int]], target: str,
                  length: int):
    """First (season, week) span of `length` consecutive `target` results."""
    if length == 0:
        return None
    run_start = 0
    run_len = 0
    for i, r in enumerate(results):
        if r == target:
            if run_len == 0:
                run_start = i
            run_len += 1
            if run_len == length:
                return weeks[run_start], weeks[i]
        else:
            run_len = 0
    return None


def _streak_detail(span) -> str:
    (start_season, start_week), (end_season, end_week) = span
    if start_season == end_season:
        if start_week == end_week:
            return f"Week {start_week}, {start_season}"
        return f"Weeks {start_week}-{end_week}, {start_season}"
    return f"Week {start_week}, {start_season} - Week {end_week}, {end_season}"


def _streak_record(data: LeagueData, m: pd.DataFrame, key: str, label: str,
                    target: str) -> dict:
    best_uid, best_len, best_span = None, 0, None
    for uid, grp in m.groupby("user_id"):
        grp = grp.sort_values(["season", "week"])
        results = list(grp["result"])
        weeks = list(zip(grp["season"], grp["week"]))
        length = longest_run(results, target)
        if length > best_len:
            best_len = length
            best_uid = uid
            best_span = _streak_span(results, weeks, target, length)
    detail = _streak_detail(best_span) if best_span else "-"
    holder = data.display(best_uid) if best_uid is not None else None
    return _record(key, label, int(best_len), holder, best_uid, detail)


def _player_extreme(pw: pd.DataFrame, data: LeagueData, key: str, label: str) -> dict:
    row = pw.loc[pw["points"].astype(float).idxmax()]
    uid = row["user_id"]
    detail = f"Week {int(row['week'])}, {int(row['season'])} - {row['player_name']}"
    return _record(key, label, _r2(row["points"]), data.display(uid), uid, detail)


def _attribute_player(data: LeagueData, season: int, player_id) -> str | None:
    """Which manager (`user_id`) is credited for a player's season: whoever
    accumulated the most of that player's points that season, from
    `player_weeks` (handles in-season trades reasonably; a player who never
    appears in `player_weeks` for that season has no attributable manager)."""
    pw = data.player_weeks
    sub = pw[(pw["season"].astype(int) == season) &
             (pw["player_id"].astype(str) == str(player_id))]
    if sub.empty:
        return None
    agg = sub.groupby("user_id")["points"].sum()
    return agg.idxmax()


def _player_season_high(data: LeagueData, key: str, label: str) -> dict:
    pp = data.player_points
    row = pp.loc[pp["points_regular"].astype(float).idxmax()]
    season = int(row["season"])
    uid = _attribute_player(data, season, row["player_id"])
    holder = data.display(uid) if uid is not None else None
    detail = f"{season} season - {row['player_name']}"
    return _record(key, label, _r2(row["points_regular"]), holder, uid, detail)


def compute_records(data: LeagueData) -> dict:
    reg = data.reg_matchups()
    dedup = _margin_rows(reg)
    nonzero = dedup[dedup["margin"] > 0]
    playoff = _playoff_matchups(data)
    standings = _played_standings(data)
    streaks_base = reg.dropna(subset=["user_id"])

    pw = data.player_weeks
    started_reg = pw[(pw["started"].astype(int) == 1) & (pw["is_playoff"].astype(int) == 0)]
    bench_reg = pw[(pw["started"].astype(int) == 0) & (pw["is_playoff"].astype(int) == 0)]

    records = [
        _team_week_extreme(reg, data, "team_week_high",
                            "Highest team score, single week (regular season)", True),
        _team_week_extreme(reg, data, "team_week_low",
                            "Lowest team score, single week (regular season)", False),
        _margin_extreme(dedup, data, "blowout",
                         "Largest margin of victory (regular season)", True),
        _margin_extreme(nonzero, data, "nailbiter",
                         "Closest margin of victory (regular season)", False),
        _season_extreme(standings, data, "season_pf_high",
                         "Most points scored, season", "points_for", True),
        _season_extreme(standings, data, "season_pf_low",
                         "Fewest points scored, season", "points_for", False),
        _season_extreme(standings, data, "season_pa_high",
                         "Most points allowed, season (the punching bag award)",
                         "points_against", True),
        _team_week_extreme(playoff, data, "playoff_week_high",
                            "Highest team score, single week (playoffs)", True),
        _streak_record(data, streaks_base, "win_streak",
                        "Longest win streak (regular season)", "W"),
        _streak_record(data, streaks_base, "loss_streak",
                        "Longest losing streak (regular season)", "L"),
        _player_extreme(started_reg, data, "player_week_high",
                         "Highest player score, single week, started (regular season)"),
        _player_season_high(data, "player_season_high",
                             "Highest player total, single season"),
        _player_extreme(bench_reg, data, "bench_week_high",
                         "Highest player score left on the bench, single week (regular season)"),
    ]

    return {"records": records}
