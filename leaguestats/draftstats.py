"""Draft analysis: was each pick worth what it cost, does draft slot predict
anything, and how do managers spend their early picks.

`surplus` mirrors the pre-migration analysis script's keeper-surplus
approach, generalized to every drafted player: a player's `points_regular`
that season minus the mean `points_regular` of every player drafted in that
same (season, round) -- keepers included in that mean, since a keeper picked
in round 6 is still "the market price" of a round-6 pick that year. Keeper
picks themselves are excluded from the steals/busts leaderboards (and their
per-manager variants) because a keeper at a discounted round is
definitionally a steal -- they get their own value table in Task 9
(`leaguestats/keepers.py`).
"""
from __future__ import annotations

import pandas as pd

from leaguestats.loading import LeagueData

_STEALS_N = 15
_BY_MANAGER_N = 5
_BUST_MAX_ROUND = 8
_TENDENCY_MAX_ROUND = 10
_QB_TIMING_MAX_ROUND = 5


def _drafted_players(data: LeagueData) -> pd.DataFrame:
    """Every draft pick from played seasons with a real player attached,
    joined to that season's `points_regular` (0 when the player was drafted
    but never scored/rostered)."""
    played = set(data.played_seasons())
    d = data.drafts.copy()
    d["season"] = d.season.astype(int)
    d = d[d.season.isin(played)]
    d = d[d.player_id.notna() & (d.player_id.astype(str) != "")].copy()
    d["round"] = d["round"].astype(int)
    d["overall_pick"] = d.overall_pick.astype(int)
    if d.is_keeper.dtype == object:
        d["is_keeper"] = d.is_keeper.astype(str).eq("True")
    else:
        d["is_keeper"] = d.is_keeper.astype(bool)

    pp = data.player_points[["season", "player_id", "points_regular"]].copy()
    pp["season"] = pp.season.astype(int)
    d = d.merge(pp, on=["season", "player_id"], how="left")
    d["points_regular"] = d["points_regular"].fillna(0.0).astype(float)

    round_avg = d.groupby(["season", "round"]).points_regular.mean().rename("round_avg")
    d = d.merge(round_avg, on=["season", "round"], how="left")
    d["surplus"] = d.points_regular - d.round_avg
    return d


def _pick_row(data: LeagueData, r) -> dict:
    return {
        "season": int(r.season),
        "manager_user": r.user_id,
        "name": data.display(r.user_id),
        "player_name": r.player_name,
        "position": r.position,
        "round": int(r.round),
        "overall_pick": int(r.overall_pick),
        "points": round(float(r.points_regular), 2),
        "surplus": round(float(r.surplus), 2),
    }


def _leaderboard(df: pd.DataFrame, n: int, ascending: bool, data: LeagueData) -> list[dict]:
    sub = df.sort_values("surplus", ascending=ascending).head(n)
    return [_pick_row(data, r) for r in sub.itertuples(index=False)]


def _by_manager(df: pd.DataFrame, n: int, ascending: bool, data: LeagueData) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for uid, grp in df.groupby("user_id"):
        out[uid] = _leaderboard(grp, n, ascending, data)
    return out


def _slot_outcomes(data: LeagueData) -> list[dict]:
    """Joins `standings`' own `draft_slot` (already the owned-slot mapping,
    post-trade) to `finish`/`champion`/`made_playoffs`. 10-team and 12-team
    eras have different slot counts, so slots > 10 only ever appear in
    12-team seasons -- `era_note` spells out which era(s), and how many
    season-rows, feed each slot's numbers."""
    s = data.standings.copy()
    s["season"] = s.season.astype(int)
    s = s[s.finish.notna() & s.draft_slot.notna()].copy()
    s["slot"] = s.draft_slot.astype(int)
    s["finish"] = s.finish.astype(float)
    s["champion"] = s.champion.fillna(0).astype(int)
    s["made_playoffs"] = s.made_playoffs.fillna(0).astype(int)
    s["era"] = s.season.apply(data.era)

    rows = []
    for slot, grp in s.groupby("slot"):
        era_counts = grp.groupby("era").size().to_dict()
        era_note = ", ".join(f"{era} (n={n})" for era, n in sorted(era_counts.items()))
        rows.append({
            "slot": int(slot),
            "n": int(len(grp)),
            "avg_finish": round(float(grp.finish.mean()), 2),
            "titles": int(grp.champion.sum()),
            "playoff_rate": round(float(grp.made_playoffs.mean()), 4),
            "era_note": era_note,
        })
    rows.sort(key=lambda r: r["slot"])
    return rows


def _by_round(d: pd.DataFrame) -> list[dict]:
    rows = []
    for rnd, grp in d.groupby("round"):
        avg = float(grp.points_regular.mean())
        hit_rate = float((grp.points_regular >= avg).mean())
        rows.append({
            "round": int(rnd),
            "avg_points": round(avg, 2),
            "hit_rate": round(hit_rate, 4),
        })
    rows.sort(key=lambda r: r["round"])
    return rows


def _finish_lookup(data: LeagueData) -> dict[tuple[int, str], int]:
    s = data.standings.copy()
    s["season"] = s.season.astype(int)
    s = s[s.finish.notna()]
    return {(int(row.season), row.user_id): int(row.finish) for row in s.itertuples(index=False)}


def _qb_timing(data: LeagueData, d: pd.DataFrame) -> list[dict]:
    """Per (season, manager): the round of their first non-keeper QB pick,
    how many non-keeper QBs they took in the first 5 rounds, and where they
    finished -- the superflex question, since this is a two-QB-startable
    league."""
    finish = _finish_lookup(data)
    non_keeper = d[~d.is_keeper]
    rows = []
    for (season, uid), grp in non_keeper.groupby(["season", "user_id"]):
        qbs = grp[grp.position == "QB"]
        if qbs.empty:
            continue
        rows.append({
            "season": int(season),
            "user_id": uid,
            "name": data.display(uid),
            "first_qb_round": int(qbs["round"].min()),
            "qbs_in_first_5": int((qbs["round"] <= _QB_TIMING_MAX_ROUND).sum()),
            "finish": finish.get((int(season), uid)),
        })
    rows.sort(key=lambda r: (r["season"], r["user_id"]))
    return rows


def _tendencies(d: pd.DataFrame) -> dict[str, dict[str, float]]:
    """user_id -> {position: share of that manager's rounds-1-10, non-keeper
    picks spent on that position}."""
    pool = d[(~d.is_keeper) & d["round"].between(1, _TENDENCY_MAX_ROUND)]
    out: dict[str, dict[str, float]] = {}
    for uid, grp in pool.groupby("user_id"):
        total = len(grp)
        counts = grp.position.value_counts()
        out[uid] = {pos: round(float(cnt) / total, 4) for pos, cnt in counts.items()}
    return out


def compute_drafts(data: LeagueData) -> dict:
    d = _drafted_players(data)
    non_keeper = d[~d.is_keeper]
    # Busts span rounds 1-8 inclusive; only late rounds are excluded by
    # design (a round-16 zero is an expected dart-throw, not a bust -- a
    # round-1 whiff is the most consequential bust there is).
    bust_pool = non_keeper[non_keeper["round"] <= _BUST_MAX_ROUND]

    return {
        "slot_outcomes": _slot_outcomes(data),
        "steals": _leaderboard(non_keeper, _STEALS_N, ascending=False, data=data),
        "busts": _leaderboard(bust_pool, _STEALS_N, ascending=True, data=data),
        "steals_by_manager": _by_manager(non_keeper, _BY_MANAGER_N, ascending=False, data=data),
        "busts_by_manager": _by_manager(bust_pool, _BY_MANAGER_N, ascending=True, data=data),
        "by_round": _by_round(d),
        "qb_timing": _qb_timing(data, d),
        "tendencies": _tendencies(d),
    }
