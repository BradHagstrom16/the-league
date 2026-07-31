"""Transactions: FAAB spending efficiency and trade outcomes.

`points_after` is the one shared notion of "production gained by an
acquisition" used everywhere below: started, non-playoff points scored by a
player for the roster that acquired it, in weeks strictly after the
transaction week, same season. Individual FAAB buys and each side of a trade
are scored identically so they're directly comparable.

Sleeper's raw transaction rows carry `roster_id`, not `user_id`, and
`roster_id` is only stable *within* a season (a roster slot gets reused by a
different manager across seasons) -- every attribution here goes through a
`(season, roster_id) -> user_id` merge onto `managers`, same pattern as
`LeagueData.reg_matchups()`/`headtohead.with_users`. `faab_bid` loads as an
object column (empty string for non-waiver rows), so it's coerced with
`pd.to_numeric(errors="coerce")` before any numeric comparison.
"""
from __future__ import annotations

import pandas as pd

from leaguestats.loading import LeagueData


def _points_after(pw: pd.DataFrame, season: int, roster_id: int, player_id: str,
                   after_week: int) -> float:
    """Started, non-playoff points scored by `player_id` for `roster_id` in
    `season`, in weeks strictly after `after_week`."""
    rows = pw[(pw.season.astype(int) == int(season)) &
              (pw.roster_id.astype(int) == int(roster_id)) &
              (pw.player_id == player_id) &
              (pw.started == 1) & (pw.is_playoff == 0) &
              (pw.week.astype(int) > int(after_week))]
    return float(rows.points.sum())


def _attribute(data: LeagueData, tx: pd.DataFrame) -> pd.DataFrame:
    """`tx` with `user_id` merged on via (season, roster_id) -> managers.
    Rows for a roster/season with no managers entry are dropped."""
    u = data.managers[["season", "roster_id", "user_id"]].copy()
    u["season"] = u.season.astype(int)
    u["roster_id"] = u.roster_id.astype(int)
    out = tx.merge(u, on=["season", "roster_id"], how="left")
    return out.dropna(subset=["user_id"])


def _completed(data: LeagueData) -> pd.DataFrame:
    """Completed transactions only, with numeric types coerced (`faab_bid`
    especially -- empty string for most rows, otherwise a bid amount) and
    `user_id` attached."""
    tx = data.transactions.copy()
    tx["faab_bid"] = pd.to_numeric(tx["faab_bid"], errors="coerce")
    tx["season"] = tx.season.astype(int)
    tx["week"] = tx.week.astype(int)
    tx["roster_id"] = tx.roster_id.astype(int)
    tx = tx[tx.status == "complete"]
    return _attribute(data, tx)


def _buys(data: LeagueData, tx: pd.DataFrame) -> list[dict]:
    """One row per completed waiver add with a positive FAAB bid."""
    pw = data.player_weeks
    rows = tx[(tx.type == "waiver") & (tx.action == "add") & (tx.faab_bid > 0)]
    buys = []
    for r in rows.itertuples(index=False):
        pa = _points_after(pw, r.season, r.roster_id, r.player_id, r.week)
        bid = float(r.faab_bid)
        buys.append(dict(
            season=int(r.season), week=int(r.week), user_id=r.user_id,
            name=data.display(r.user_id), player_name=r.player_name,
            bid=bid, points_after=round(pa, 2), ppd=round(pa / bid, 2),
        ))
    return buys


def _faab_seasons(buys: list[dict]) -> dict[int, list[dict]]:
    """Per-season, per-user FAAB summary: total spent, total points_after
    across all of that user's buys that season, and the resulting ppd."""
    grouped: dict[tuple[int, str], list[dict]] = {}
    for b in buys:
        grouped.setdefault((b["season"], b["user_id"]), []).append(b)

    out: dict[int, list[dict]] = {}
    for (season, uid), items in grouped.items():
        spent = sum(i["bid"] for i in items)
        points_after = sum(i["points_after"] for i in items)
        out.setdefault(season, []).append(dict(
            user_id=uid, name=items[0]["name"], spent=spent,
            points_after=round(points_after, 2),
            ppd=round(points_after / spent, 2),
        ))
    for season in out:
        out[season].sort(key=lambda r: r["points_after"], reverse=True)
    return out


def _pickups(data: LeagueData, tx: pd.DataFrame) -> list[dict]:
    """Top 10 adds by points_after, across waiver *and* free-agent adds
    (unlike `_buys`, no bid filter -- $0 free-agent pickups are included)."""
    pw = data.player_weeks
    rows = tx[tx.type.isin(["waiver", "free_agent"]) & (tx.action == "add")]
    picks = []
    for r in rows.itertuples(index=False):
        pa = _points_after(pw, r.season, r.roster_id, r.player_id, r.week)
        bid = float(r.faab_bid) if pd.notna(r.faab_bid) and r.faab_bid > 0 else 0.0
        picks.append(dict(
            season=int(r.season), week=int(r.week), user_id=r.user_id,
            name=data.display(r.user_id), player_name=r.player_name,
            bid=bid, points_after=round(pa, 2),
            ppd=round(pa / bid, 2) if bid else None,
        ))
    picks.sort(key=lambda r: r["points_after"], reverse=True)
    return picks[:10]


def trade_ledger(data: LeagueData) -> list[dict]:
    """One entry per completed trade, chronological. Each side is a distinct
    roster_id in the transaction group; `players_gained` is that side's `add`
    rows. Two-plus-team trades fall out naturally since sides is a list.
    `winner_user_id` is the side with the larger points_after; `margin` is
    the gap between the winner and the runner-up side."""
    tx = _completed(data)
    pw = data.player_weeks
    trades = tx[tx.type == "trade"]

    out = []
    for tid, g in trades.groupby("transaction_id", sort=False):
        season = int(g.season.iloc[0])
        week = int(g.week.iloc[0])
        date = g.created_date.iloc[0]

        sides = []
        for roster_id, rg in g.groupby("roster_id"):
            uid = rg.user_id.iloc[0]
            gained = rg[rg.action == "add"]
            points_after = sum(
                _points_after(pw, season, roster_id, pid, week)
                for pid in gained.player_id
            )
            sides.append(dict(
                user_id=uid, name=data.display(uid),
                players_gained=list(gained.player_name),
                points_after=round(points_after, 2),
            ))
        if len(sides) < 2:
            continue  # incomplete trade record (e.g. missing roster/season)

        ranked = sorted(sides, key=lambda s: s["points_after"], reverse=True)
        margin = round(ranked[0]["points_after"] - ranked[1]["points_after"], 2)
        out.append(dict(
            transaction_id=str(tid), season=season, week=week, date=date,
            sides=sides, winner_user_id=ranked[0]["user_id"], margin=margin,
        ))

    out.sort(key=lambda t: (t["season"], t["week"], t["transaction_id"]))
    return out


def _activity(tx: pd.DataFrame) -> dict[str, dict]:
    """Career adds/drops (every completed transaction row, any type) and
    trades (distinct completed trade transaction_ids the user's roster
    participated in) per user."""
    activity: dict[str, dict[str, int]] = {}

    def bump(uid: str, key: str) -> None:
        activity.setdefault(uid, {"adds": 0, "drops": 0, "trades": 0})[key] += 1

    for r in tx.itertuples(index=False):
        if r.action == "add":
            bump(r.user_id, "adds")
        elif r.action == "drop":
            bump(r.user_id, "drops")

    trades = tx[tx.type == "trade"][["user_id", "transaction_id"]].drop_duplicates()
    for r in trades.itertuples(index=False):
        bump(r.user_id, "trades")

    return activity


def compute_transactions(data: LeagueData) -> dict:
    tx = _completed(data)
    buys = _buys(data, tx)

    ranked = sorted(buys, key=lambda b: b["ppd"], reverse=True)
    worst_pool = sorted((b for b in buys if b["bid"] >= 10), key=lambda b: b["ppd"])

    return {
        "faab_seasons": _faab_seasons(buys),
        "best_buys": ranked[:10],
        "worst_buys": worst_pool[:10],
        "pickups": _pickups(data, tx),
        "trades": trade_ledger(data),
        "activity": _activity(tx),
    }
