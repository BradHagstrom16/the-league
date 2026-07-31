#!/usr/bin/env python3
"""
Build the site: load CSVs, compute every stat, write site/data/*.json.

Page rendering hangs off build_pages() (added by the site tasks); the JSON
payloads are the single source every page reads from.
"""

import json
import os
from pathlib import Path

from leaguestats.career import compute_career
from leaguestats.draftstats import compute_drafts
from leaguestats.headtohead import compute_h2h
from leaguestats.keepers import compute_keepers
from leaguestats.lineups import compute_lineups
from leaguestats.loading import load_data, write_name_template
from leaguestats.luck import compute_luck
from leaguestats.recordbook import compute_records
from leaguestats.txstats import compute_transactions
from leaguestats.util import to_jsonable

ROOT = Path(__file__).parent
SITE = ROOT / "site"
SITE_DATA = SITE / "data"

ERA_BOUNDARY = 2025  # first 12-team season

MODULES = {
    "career": compute_career,
    "h2h": compute_h2h,
    "luck": compute_luck,
    "lineups": compute_lineups,
    "drafts": compute_drafts,
    "keepers": compute_keepers,
    "transactions": compute_transactions,
    "records": compute_records,
}


def build_json():
    """Load data, run every stats module, write site/data/*.json.

    Returns the full payload dict (module name -> computed dict) so the
    page renderers reuse the same objects without re-reading JSON.
    """
    write_name_template(ROOT)
    data = load_data(ROOT)

    payload = {name: to_jsonable(fn(data)) for name, fn in MODULES.items()}

    newest = data.settings.sort_values("season").iloc[-1]
    payload["meta"] = to_jsonable({
        "league_name": newest["name"],
        "seasons": data.played_seasons(),
        "current_season": int(newest.season),
        "league_status": newest.status,
        "generated_utc": os.environ.get("BUILD_TIME", ""),
        "lore": data.lore,
        "era_boundary": ERA_BOUNDARY,
    })

    SITE_DATA.mkdir(parents=True, exist_ok=True)
    for name, obj in payload.items():
        (SITE_DATA / f"{name}.json").write_text(
            json.dumps(obj, indent=1) + "\n")

    payload["_data"] = data  # for renderers; never serialized
    return payload


def _users(payload):
    """Ordered manager directory: rotation numbers, slugs, avatar lookup."""
    from leaguestats.render import slug as _slug
    managers = payload["career"]["managers"]
    ordered = sorted(managers, key=lambda m: -(m["wins"] + m["losses"] + m["ties"]))
    seen, out = {}, {}
    for i, m in enumerate(ordered):
        s = _slug(m["name"]) or _slug(m["handle"]) or m["user_id"]
        if s in seen:
            s = f"{s}-{m['user_id'][-4:]}"
        seen[s] = True
        out[m["user_id"]] = {**m, "slug": s, "rot": 501 + i}
    return out


def _season_ctx(payload, data, season):
    """Everything the per-season page needs."""
    import pandas as pd
    users = payload["_users"]
    st = data.standings
    st = st[(st.season.astype(int) == season) & st.finish.notna()].sort_values("finish")
    luck_rows = {r["user_id"]: r for r in payload["luck"]["seasons"].get(str(season), [])}
    standings = [{**r, "luck": luck_rows.get(r["user_id"], {}).get("luck_delta")}
                 for r in st.to_dict("records")]

    m = data.matchups
    m = m[m.season.astype(int) == season].copy()
    m["week"] = m.week.astype(int)
    r2u = data.r2u(season)
    m["user_id"] = m.roster_id.astype(int).map(r2u)
    m["opp_user"] = m.opponent_roster_id.astype(int).map(r2u)
    col_users = [r["user_id"] for r in standings]
    weeks = sorted(m.week.unique())
    grid = []
    for wk in weeks:
        wrows = {r.user_id: r for r in m[m.week == wk].itertuples()}
        grid.append({
            "week": wk,
            "playoff": bool(next(iter(wrows.values())).is_playoff) if wrows else False,
            "cells": [
                (lambda r: {"pts": r.points, "result": r.result,
                            "opp": users.get(r.opp_user, {}).get("name", "?")}
                 )(wrows[u]) if u in wrows else None
                for u in col_users
            ],
        })

    br = data.brackets
    br = br[(br.season.astype(int) == season) & (br.bracket == "winners")]
    rounds = {}
    playoff_start = int(data.settings[data.settings.season.astype(int) == season]
                        .iloc[0].playoff_week_start)
    pm = m[m.is_playoff.astype(bool)]
    for r in br.itertuples():
        if pd.isna(r.winner) or str(r.winner) == "":
            continue
        rid_w = int(float(r.winner))
        rid_l = int(float(r.loser)) if str(r.loser) not in ("", "nan") else None
        wk = playoff_start + int(r.round) - 1
        score = ""
        if rid_l is not None:
            hit = pm[(pm.week == wk) & (pm.roster_id.astype(int) == rid_w)
                     & (pm.opponent_roster_id.astype(int) == rid_l)]
            if len(hit):
                h = hit.iloc[0]
                score = f"{h.points:g}–{h.opponent_points:g}"
        rounds.setdefault(int(r.round), []).append({
            "winner": users.get(r2u.get(rid_w), {}),
            "loser": users.get(r2u.get(rid_l), {}) if rid_l is not None else None,
            "score": score,
            "position": int(r.position) if str(r.position) not in ("", "nan") else None,
        })

    superla = []
    if luck_rows:
        lucky = max(luck_rows.values(), key=lambda r: r["luck_delta"])
        unlucky = min(luck_rows.values(), key=lambda r: r["luck_delta"])
        superla = [
            ("Luckiest", users.get(lucky["user_id"], {}).get("name"),
             f"{lucky['luck_delta']:+.2f} wins vs schedule-neutral"),
            ("Unluckiest", users.get(unlucky["user_id"], {}).get("name"),
             f"{unlucky['luck_delta']:+.2f} wins vs schedule-neutral"),
        ]
    hi = m[~m.is_playoff.astype(bool)].nlargest(1, "points")
    if len(hi):
        h = hi.iloc[0]
        superla.insert(0, ("High week", users.get(h.user_id, {}).get("name"),
                           f"{h.points:g} in week {h.week}"))
    return {"standings": standings, "grid": grid, "col_users": col_users,
            "rounds": rounds, "superlatives": superla}


def build_pages(payload):
    """Render every HTML page from the computed payload. Returns paths."""
    from leaguestats import charts
    from leaguestats.render import render_page

    data = payload["_data"]
    users = _users(payload)
    payload["_users"] = users
    meta = payload["meta"]
    seasons = payload["meta"]["seasons"]
    lore = meta.get("lore") or {}
    written = []

    def page(template, out_rel, ctx, root=""):
        out = SITE / out_rel
        render_page(template, {"root": root, "meta": meta, "users": users,
                               "lore": lore, "charts": charts, **ctx}, out)
        written.append(out)

    # ---- index -----------------------------------------------------------
    rec = {r["key"]: r for r in payload["records"]["records"]}
    reigning = payload["career"]["seasons"][-1]
    last_place = {"user_id": reigning["last_user"], "name": reigning["last_name"]}
    marquee = [rec[k] for k in ("team_week_high", "blowout", "win_streak",
                                "season_pf_high") if k in rec]
    page("index.html.j2", "index.html", {
        "active": "board",
        "status": meta["league_status"],
        "career": payload["career"],
        "reigning": reigning,
        "last_place": last_place,
        "marquee": marquee,
        "declared": payload["keepers"]["declared_next"],
        "rules": payload["keepers"]["rules"],
    })

    # ---- records -----------------------------------------------------------
    groups = [
        ("Game lines", ["team_week_high", "team_week_low", "blowout",
                        "nailbiter", "playoff_week_high"]),
        ("Season lines", ["season_pf_high", "season_pf_low", "season_pa_high"]),
        ("Streaks", ["win_streak", "loss_streak"]),
        ("Player lines", ["player_week_high", "player_season_high",
                          "bench_week_high"]),
    ]
    page("records.html.j2", "records.html", {
        "active": "records",
        "groups": [(t, [rec[k] for k in ks if k in rec]) for t, ks in groups],
    })

    # ---- seasons ------------------------------------------------------------
    page("seasons.html.j2", "seasons.html", {
        "active": "seasons",
        "season_rows": payload["career"]["seasons"],
    })
    for season in seasons:
        ctx = _season_ctx(payload, data, season)
        page("season.html.j2", f"seasons/{season}.html",
             {"active": "seasons", "season": season, **ctx}, root="../")

    # ---- managers ------------------------------------------------------------
    page("managers.html.j2", "managers.html", {
        "active": "managers",
        "roster": sorted(users.values(), key=lambda u: u["rot"]),
    })
    teams_by_season = dict(zip(data.settings.season.astype(int),
                               data.settings.teams.astype(int)))
    med_by_season = {s: (teams_by_season.get(s, 12) + 1) / 2 for s in seasons}
    fby = payload["career"]["finish_by_year"]
    luck_car = {r["user_id"]: r for r in payload["luck"]["career"]}
    lin_car = {r["user_id"]: r for r in payload["lineups"]["career"]}
    for uid, u in users.items():
        finishes = [fby.get(uid, {}).get(str(s)) for s in seasons]
        medians = [med_by_season[s] for s in seasons]
        chart = charts.svg_line(
            [(u["name"], finishes), ("League median", medians)],
            [str(s) for s in seasons], y_invert=True, h=240)
        h2h_rows = []
        for oid, cell in payload["h2h"]["grid"].get(uid, {}).items():
            if oid in users:
                h2h_rows.append({"opp": users[oid], **cell})
        h2h_rows.sort(key=lambda r: r["opp"]["rot"])
        faab_spent = sum(r["spent"] for rows in payload["transactions"]
                         ["faab_seasons"].values()
                         for r in rows if r["user_id"] == uid)
        page("manager.html.j2", f"managers/{u['slug']}.html", {
            "active": "managers",
            "m": u,
            "chart": chart,
            "h2h_rows": h2h_rows,
            "luck": luck_car.get(uid),
            "lineup": lin_car.get(uid),
            "faab_spent": faab_spent,
            "steals": payload["drafts"].get("steals_by_manager", {}).get(uid, [])[:3],
            "busts": payload["drafts"].get("busts_by_manager", {}).get(uid, [])[:3],
            "keeps": [v for v in payload["keepers"]["value"] if v["user_id"] == uid],
            "benchings": [b for b in payload["lineups"]["worst_benchings"]
                          if b["user_id"] == uid],
        }, root="../")

    # ---- h2h -----------------------------------------------------------------
    ordered = [u for u in sorted(users.values(), key=lambda x: x["rot"])]
    labels = [u["name"] for u in ordered]
    values = {}
    for a in ordered:
        for b in ordered:
            if a["user_id"] == b["user_id"]:
                values[(a["name"], b["name"])] = None
                continue
            cell = payload["h2h"]["grid"].get(a["user_id"], {}).get(b["user_id"])
            if not cell:
                values[(a["name"], b["name"])] = None
                continue
            g = cell["w"] + cell["l"] + cell["t"]
            values[(a["name"], b["name"])] = (cell["w"] + 0.5 * cell["t"]) / g if g else None
    heat = charts.svg_heatmap(labels, labels, values, cell=42)
    pairs = []
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            key = "|".join(sorted([a["user_id"], b["user_id"]]))
            log = payload["h2h"]["pairs"].get(key)
            if not log:
                continue
            first, second = sorted([a["user_id"], b["user_id"]])
            split = payload["h2h"]["reg_playoff_split"].get(key, {})
            pairs.append({
                "a": users[first], "b": users[second],
                "anchor": f"{users[first]['slug']}-vs-{users[second]['slug']}",
                "grid": payload["h2h"]["grid"][first][second],
                "split": split, "log": log,
            })
    page("h2h.html.j2", "h2h.html", {"active": "h2h", "heat": heat,
                                     "pairs": pairs, "ordered": ordered})

    # ---- draft & keepers --------------------------------------------------
    d = payload["drafts"]
    by_round_chart = charts.svg_bar(
        [(str(r["round"]), r["avg_points"]) for r in d["by_round"]], h=240)
    audit = payload["keepers"]["audit"]
    flagged = [a for a in audit if not a["charged_ok"] or not a["eligible_round"]
               or a["repeat_keep"]]
    page("draft.html.j2", "draft.html", {
        "active": "draft",
        "d": d, "by_round_chart": by_round_chart,
        "keepers": payload["keepers"], "flagged": flagged,
        "summary": payload["keepers"]["summary"],
    })

    # ---- trades & waivers ----------------------------------------------------
    tx = payload["transactions"]
    faab_years = sorted(tx["faab_seasons"].keys(), reverse=True)
    page("trades.html.j2", "trades.html", {
        "active": "trades", "tx": tx, "faab_years": faab_years,
    })

    # ---- champions & shame -----------------------------------------------
    page("champions.html.j2", "champions.html", {
        "active": "champions",
        "season_rows": payload["career"]["seasons"],
        "trophy": lore.get("trophy_name") or "",
        "punishments": lore.get("punishments") or {},
        "notes": lore.get("champion_notes") or {},
    })
    return written


if __name__ == "__main__":
    out = build_json()
    pages = build_pages(out)
    n = sum(1 for k in out if not k.startswith("_"))
    print(f"site/data: {n} JSON payloads; {len(pages)} pages rendered")
