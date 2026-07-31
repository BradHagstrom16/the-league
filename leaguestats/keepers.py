"""Keeper-rule audit and keeper value analysis.

The league's four keeper rules (verbatim, also returned by `compute_keepers`
under the `rules` key so the site can render them next to the data they
govern):

1. A manager may keep 2 players maximum.
2. The player must have been drafted in the previous year's draft in round
   6 or later. A player may not be kept two years in a row.
3. You keep a player at the round you drafted him — one round earlier if
   he ever left your roster (trade, drop and re-claim, or any acquisition
   from another manager).
4. Draft pick trading is allowed before and during the draft, including
   keepers. Future years' picks cannot be traded.

`left_roster`/`audit_keepers` port the same logic the league's offline
analyzer used (see ggg-league's `analyze_league.py`), adapted to the
`LeagueData` interface: `r2u()`/`display()` replace the ad hoc roster-id and
name lookups, and every season/round comparison is defensively cast to int
since real CSVs load those as int64 but a hand-built fixture might not.
"""
from __future__ import annotations

import pandas as pd

from leaguestats.loading import LeagueData

KEEPER_MIN_ROUND = 6
MAX_KEEPERS = 2

RULES = [
    "A manager may keep 2 players maximum.",
    "The player must have been drafted in the previous year's draft in "
    "round 6 or later. A player may not be kept two years in a row.",
    "You keep a player at the round you drafted him — one round earlier "
    "if he ever left your roster (trade, drop and re-claim, or any "
    "acquisition from another manager).",
    "Draft pick trading is allowed before and during the draft, including "
    "keepers. Future years' picks cannot be traded.",
]


def _draft_start_ms(data: LeagueData, season: int):
    """That season's draft_start_ms, or NaN if the season (or the column
    value) is missing -- some seasons' settings rows may not have it."""
    s = data.settings
    row = s[s.season.astype(int) == int(season)]
    if not len(row):
        return float("nan")
    return row.iloc[0].draft_start_ms


def left_roster(data: LeagueData, season: int, player_id: str, user_id: str) -> bool:
    """Did this player leave `user_id`'s roster at some point during `season`?

    True if either (a) that season's draft shows a *different* user
    drafting him (he was already on someone else's roster before the
    season's transactions even start), or (b) a completed drop, or any
    completed trade row, moves that player off a roster owned by
    `user_id`, at/after that season's draft_start_ms (the filter is
    skipped when draft_start_ms is unknown for the season).
    """
    drafts = data.drafts
    prior = drafts[(drafts.season.astype(int) == int(season)) &
                   (drafts.player_id.astype(str) == str(player_id))]
    if len(prior) and prior.iloc[0].user_id != user_id:
        return True

    t = data.transactions
    t = t[(t.season.astype(int) == int(season)) & (t.status == "complete") &
          (t.player_id.astype(str) == str(player_id))]
    ds = _draft_start_ms(data, season)
    if pd.notna(ds):
        t = t[t.created_ms >= ds]
    gone = t[(t.action == "drop") | (t.type == "trade")]

    r2u = data.r2u(season)
    return any(r2u.get(int(r)) == user_id for r in gone.roster_id)


def audit_keepers(data: LeagueData) -> list[dict]:
    """One row per keeper pick that has a prior-season draft record (a
    keeper with no such record -- e.g. a league's very first keeper class,
    or a data gap -- can't be graded and is skipped).

    Graded only for played seasons (`data.played_seasons()`): a `pre_draft`
    season's keepers (e.g. next year's declared-but-not-yet-drafted picks)
    haven't happened yet, so they aren't audited/summarized here -- they
    surface only via `declared_next`. `by_season` (the prior-season lookup
    a keeper is graded against) still indexes *all* seasons regardless of
    status, since a played season's prior year is always itself played.
    """
    drafts = data.drafts.copy()
    drafts["season"] = drafts.season.astype(int)
    by_season = {season: grp.set_index("player_id")
                 for season, grp in drafts.groupby("season")}
    played = set(data.played_seasons())

    rows = []
    for k in drafts[drafts.is_keeper & drafts.season.isin(played)].itertuples(index=False):
        prev = by_season.get(int(k.season) - 1)
        if prev is None or k.player_id not in prev.index:
            continue
        p = prev.loc[k.player_id]
        if isinstance(p, pd.DataFrame):  # duplicate player_id in one draft: take first
            p = p.iloc[0]

        prev_round = int(p["round"])
        left = left_roster(data, int(k.season) - 1, k.player_id, k.user_id)
        need = prev_round - 1 if left else prev_round
        keep_round = int(k.round)

        rows.append({
            "season": int(k.season),
            "user_id": k.user_id,
            "name": data.display(k.user_id),
            "player_id": k.player_id,
            "player_name": k.player_name,
            "prev_round": prev_round,
            "keep_round": keep_round,
            "left": bool(left),
            "need": int(need),
            "charged_ok": bool(keep_round == need),
            "eligible_round": bool(prev_round >= KEEPER_MIN_ROUND),
            "repeat_keep": bool(p["is_keeper"]),
        })

    rows.sort(key=lambda r: (r["season"], str(r["user_id"]), str(r["player_id"])))
    return rows


def _drafts_with_points(data: LeagueData) -> pd.DataFrame:
    """Drafted players in played seasons only, merged with that season's
    regular-season fantasy points (0 for a player with no points_regular
    row, e.g. never active)."""
    played = set(data.played_seasons())
    d = data.drafts.copy()
    d["season"] = d.season.astype(int)
    d = d[d.season.isin(played)]

    pts = data.player_points[["season", "player_id", "points_regular"]].copy()
    pts["season"] = pts.season.astype(int)

    d = d.merge(pts, on=["season", "player_id"], how="left")
    d["points_regular"] = d.points_regular.fillna(0.0)
    return d


def _rule_flags(data: LeagueData, audit: list[dict]) -> dict:
    """Counts of how often each numbered rule was actually violated.

    `max_keepers_exceeded` is checked against every keeper pick in the raw
    drafts data -- deliberately including a `pre_draft` season, unlike the
    other three flags below: rule 1's 2-keeper cap is a declaration-time
    constraint, so over-declaring for next year is a real, checkable
    violation the moment it's declared, not something that waits for the
    season to be played. Do not "fix" this to `played`-only without
    revisiting that intent. The other three come from the already
    played-seasons-only graded `audit` rows: `ineligible_round` (rule 2,
    first clause), `repeat_keep` (rule 2, second clause), and
    `wrong_round_charge` (rule 3).
    """
    drafts = data.drafts.copy()
    drafts["season"] = drafts.season.astype(int)
    keeper_counts = drafts[drafts.is_keeper].groupby(["season", "user_id"]).size()

    return {
        "max_keepers_exceeded": int((keeper_counts > MAX_KEEPERS).sum()),
        "ineligible_round": sum(1 for r in audit if not r["eligible_round"]),
        "repeat_keep": sum(1 for r in audit if r["repeat_keep"]),
        "wrong_round_charge": sum(1 for r in audit if not r["charged_ok"]),
    }


def _declared_next(data: LeagueData) -> list[dict]:
    """Keeper picks already declared for the newest not-yet-drafted season:
    the newest `pre_draft` season in `settings` whose draft CSV actually has
    keeper rows. `[]` if there's no such season."""
    settings = data.settings.copy()
    settings["season"] = settings.season.astype(int)
    pre_draft_seasons = sorted(
        settings[settings.status == "pre_draft"].season.tolist(), reverse=True)

    drafts = data.drafts.copy()
    drafts["season"] = drafts.season.astype(int)

    for season in pre_draft_seasons:
        rows = drafts[(drafts.season == season) & drafts.is_keeper]
        if not len(rows):
            continue
        out = [{
            "user_id": row.user_id,
            "name": data.display(row.user_id),
            "player_name": row.player_name,
            "round": int(row.round),
        } for row in rows.itertuples(index=False)]
        out.sort(key=lambda r: r["round"])
        return out
    return []


def compute_keepers(data: LeagueData) -> dict:
    audit = audit_keepers(data)
    n = len(audit)
    charged_ok = sum(1 for r in audit if r["charged_ok"])
    summary = {"n": n, "charged_ok": charged_ok, "rule_flags": _rule_flags(data, audit)}

    dp = _drafts_with_points(data)
    round_avg = (dp.groupby(["season", "round"]).points_regular.mean()
                 .rename("round_avg").reset_index())
    kept = dp[dp.is_keeper].merge(round_avg, on=["season", "round"], how="left")
    kept = kept.assign(surplus=(kept.points_regular - kept.round_avg).round(1))

    value = [{
        "season": int(row.season),
        "user_id": row.user_id,
        "name": data.display(row.user_id),
        "player_name": row.player_name,
        "keep_round": int(row.round),
        "points": round(float(row.points_regular), 1),
        "surplus": round(float(row.surplus), 1),
    } for row in kept.itertuples(index=False)]
    value.sort(key=lambda r: r["surplus"], reverse=True)

    by_manager = []
    if len(kept):
        hit = kept.surplus > 0
        grp = kept.assign(hit=hit).groupby("user_id").agg(
            keeps=("surplus", "size"),
            avg_surplus=("surplus", "mean"),
            hit_rate=("hit", "mean"),
        ).reset_index()
        by_manager = [{
            "user_id": row.user_id,
            "name": data.display(row.user_id),
            "keeps": int(row.keeps),
            "avg_surplus": round(float(row.avg_surplus), 2),
            "hit_rate": round(float(row.hit_rate), 4),
        } for row in grp.itertuples(index=False)]
        by_manager.sort(key=lambda r: r["avg_surplus"], reverse=True)

    return {
        "rules": list(RULES),
        "audit": audit,
        "summary": summary,
        "value": value,
        "by_manager": by_manager,
        "declared_next": _declared_next(data),
    }
