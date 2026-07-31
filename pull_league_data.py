#!/usr/bin/env python3
"""
Pull all available Sleeper history for The League.

Sleeper's read API is public — no auth, no cookies, no credentials. League
history is a linked list: each season's league object carries a
`previous_league_id`, so we walk the chain back from the current season.

Outputs CSVs into subdirectories under data/. Adapted from the ggg-league
puller (github.com/atmoore/ggg-league), with three additions: per-player
per-week scoring rows (player_weeks), playoff bracket rows, and transaction
ids on transaction rows.
"""

import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

# The 2026 season of The League. Everything else is discovered by walking
# previous_league_id, so only this ID needs updating each new season.
ROOT_LEAGUE_ID = "1315570882550202368"

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = BASE_DIR / ".cache"

API = "https://api.sleeper.app/v1"

# Sleeper matchup weeks. We pull the full range and tag playoff weeks using
# each season's playoff_week_start rather than assuming a fixed schedule.
MAX_WEEK = 18

errors = []


def note_error(ctx, exc):
    msg = f"{ctx}: {exc}"
    print(f"  [SKIP] {msg}")
    errors.append(msg)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def get(path, retries=3):
    """GET {API}/{path} -> parsed JSON (None if Sleeper 404s / returns null)."""
    url = f"{API}/{path}"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    return None


def load_players():
    """
    The NFL player dictionary (~10 MB). Sleeper asks that this be called at most
    once per day, so it is cached on disk and reused.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    cache = CACHE_DIR / "players_nfl.json"
    if cache.exists() and (time.time() - cache.stat().st_mtime) < 86400:
        return json.loads(cache.read_text())
    print("  fetching player dictionary (~10MB, cached 24h)...")
    players = get("players/nfl")
    cache.write_text(json.dumps(players))
    return players


def player_name(players, pid):
    p = players.get(str(pid)) or {}
    full = p.get("full_name")
    if full:
        return full
    # Defenses come through as team abbreviations with no full_name.
    first, last = p.get("first_name", ""), p.get("last_name", "")
    return f"{first} {last}".strip() or str(pid)


def player_pos(players, pid):
    p = players.get(str(pid)) or {}
    return p.get("position") or ""


# ---------------------------------------------------------------------------
# Season discovery
# ---------------------------------------------------------------------------
def discover_seasons(root_id):
    """Walk previous_league_id back through time. Returns oldest -> newest."""
    seasons = []
    lid = root_id
    seen = set()
    while lid and lid not in ("0", "") and lid not in seen:
        seen.add(lid)
        league = get(f"league/{lid}")
        if not league:
            break
        seasons.append(league)
        lid = league.get("previous_league_id")
    seasons.reverse()
    return seasons


def team_index(league_id):
    """
    roster_id -> {manager, team_name, user_id}.

    Sleeper separates the *user* (a person, with a display_name) from the
    *roster* (their team). Team names live in user metadata and are optional,
    so fall back to the display name.
    """
    users = get(f"league/{league_id}/users") or []
    rosters = get(f"league/{league_id}/rosters") or []

    by_user = {}
    for u in users:
        meta = u.get("metadata") or {}
        by_user[u["user_id"]] = {
            "manager": u.get("display_name") or "",
            "team_name": meta.get("team_name") or u.get("display_name") or "",
            "avatar": u.get("avatar") or "",
        }

    idx = {}
    for r in rosters:
        info = by_user.get(r.get("owner_id"), {})
        idx[r["roster_id"]] = {
            "manager": info.get("manager", ""),
            "team_name": info.get("team_name", ""),
            "user_id": r.get("owner_id") or "",
            "avatar": info.get("avatar", ""),
        }
    return idx, rosters


def fpts(settings, key="fpts"):
    """Sleeper stores points split into integer + decimal fields."""
    whole = settings.get(key) or 0
    dec = settings.get(f"{key}_decimal") or 0
    return round(whole + dec / 100, 2)


def champion_of(league_id):
    """Return (champion_roster_id, runner_up_roster_id, third_roster_id)."""
    bracket = get(f"league/{league_id}/winners_bracket") or []
    champ = runner = third = None
    for m in bracket:
        if m.get("p") == 1:
            champ, runner = m.get("w"), m.get("l")
        elif m.get("p") == 3:
            third = m.get("w")
    return champ, runner, third


def write_csv(path, fields, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# 1. DRAFTS  (incl. keeper flags — the whole point of this repo)
# ---------------------------------------------------------------------------
DRAFT_FIELDS = [
    "season", "round", "pick_in_round", "overall_pick", "draft_slot",
    "slot_owner_roster_id", "roster_id", "traded_pick", "user_id", "manager", "team_name",
    "player_id", "player_name", "position", "nfl_team", "years_exp", "is_keeper",
]


def pull_drafts(seasons, players):
    out_dir = DATA_DIR / "drafts"
    out_dir.mkdir(exist_ok=True)
    all_rows = []

    for league in seasons:
        season = league["season"]
        draft_id = league.get("draft_id")
        try:
            idx, _ = team_index(league["league_id"])
            picks = get(f"draft/{draft_id}/picks") or []
            if not picks:
                note_error(f"draft_{season}", "no picks (draft not started)")
                continue

            # Picks get traded, so the roster that MADE a pick is not
            # necessarily the roster that owned that draft slot. slot_to_roster_id
            # is the draft's own slot->owner map and survives pick trades; the
            # roster_id on a pick object does not.
            draft_meta = get(f"draft/{draft_id}") or {}
            slot_owner = {int(k): v for k, v in
                          (draft_meta.get("slot_to_roster_id") or {}).items()}
            # Needed downstream to tell offseason moves from in-season ones.
            league["_draft_start"] = draft_meta.get("start_time")

            rows = []
            for p in picks:
                meta = p.get("metadata") or {}
                t = idx.get(p.get("roster_id"), {})
                name = f"{meta.get('first_name','')} {meta.get('last_name','')}".strip()
                rows.append({
                    "season": season,
                    "round": p.get("round"),
                    "pick_in_round": p.get("draft_slot"),
                    "overall_pick": p.get("pick_no"),
                    "draft_slot": p.get("draft_slot"),
                    "slot_owner_roster_id": slot_owner.get(p.get("draft_slot"), ""),
                    "roster_id": p.get("roster_id"),
                    "traded_pick": int(
                        slot_owner.get(p.get("draft_slot")) is not None
                        and slot_owner.get(p.get("draft_slot")) != p.get("roster_id")
                    ),
                    "user_id": t.get("user_id", ""),
                    "manager": t.get("manager", ""),
                    "team_name": t.get("team_name", ""),
                    "player_id": p.get("player_id"),
                    "player_name": name or player_name(players, p.get("player_id")),
                    "position": meta.get("position") or player_pos(players, p.get("player_id")),
                    "nfl_team": meta.get("team") or "",
                    "years_exp": meta.get("years_exp") or "",
                    # Sleeper uses null for non-keepers, not False.
                    "is_keeper": bool(p.get("is_keeper")),
                })

            rows.sort(key=lambda r: r["overall_pick"] or 0)
            write_csv(out_dir / f"draft_{season}.csv", DRAFT_FIELDS, rows)
            all_rows.extend(rows)
            nk = sum(1 for r in rows if r["is_keeper"])
            print(f"  drafts/{season}: {len(rows)} picks ({nk} keepers)")
        except Exception as e:
            note_error(f"draft_{season}", e)

    write_csv(DATA_DIR / "drafts_all.csv", DRAFT_FIELDS, all_rows)
    print(f"  drafts_all.csv: {len(all_rows)} picks")
    return all_rows


# ---------------------------------------------------------------------------
# 2. STANDINGS  (points for / against — the "pf" ask)
# ---------------------------------------------------------------------------
STANDING_FIELDS = [
    "season", "roster_id", "user_id", "manager", "team_name", "wins", "losses", "ties",
    "points_for", "points_against", "potential_points", "efficiency",
    "draft_slot", "finish", "champion", "made_playoffs",
    "waiver_budget_used", "total_moves",
]


def pull_standings(seasons, draft_rows):
    out_dir = DATA_DIR / "standings"
    out_dir.mkdir(exist_ok=True)
    all_rows = []

    # roster_id -> the draft slot that roster OWNED (not who used it; picks trade).
    slot_by_season = {}
    for r in draft_rows:
        if r["round"] == 1 and r["slot_owner_roster_id"] != "":
            slot_by_season.setdefault(r["season"], {})[r["slot_owner_roster_id"]] = r["draft_slot"]

    for league in seasons:
        season = league["season"]
        try:
            idx, rosters = team_index(league["league_id"])
            champ, runner, third = champion_of(league["league_id"])
            playoff_teams = (league.get("settings") or {}).get("playoff_teams", 6)

            rows = []
            for r in rosters:
                s = r.get("settings") or {}
                rid = r["roster_id"]
                t = idx.get(rid, {})
                pf = fpts(s, "fpts")
                pp = fpts(s, "ppts")
                rows.append({
                    "season": season,
                    "roster_id": rid,
                    "user_id": t.get("user_id", ""),
                    "manager": t.get("manager", ""),
                    "team_name": t.get("team_name", ""),
                    "wins": s.get("wins", 0),
                    "losses": s.get("losses", 0),
                    "ties": s.get("ties", 0),
                    "points_for": pf,
                    "points_against": fpts(s, "fpts_against"),
                    "potential_points": pp,
                    # How much of your ceiling you actually started.
                    "efficiency": round(pf / pp, 4) if pp else "",
                    "draft_slot": slot_by_season.get(season, {}).get(rid, ""),
                    "finish": "",
                    "champion": int(rid == champ) if champ else 0,
                    "made_playoffs": "",
                    "waiver_budget_used": s.get("waiver_budget_used", 0),
                    "total_moves": s.get("total_moves", 0),
                })

            # Sleeper exposes no regular-season rank field, so derive it the way
            # the league does: wins first, points for as the tiebreak. Skip
            # seasons that have not been played — 0-0 records would rank teams
            # by nothing and read as a real standing.
            played = any(r["wins"] or r["losses"] or r["ties"] for r in rows)
            rows.sort(key=lambda r: (-r["wins"], -r["points_for"]))
            if played:
                for i, r in enumerate(rows, 1):
                    r["finish"] = i
                    r["made_playoffs"] = int(i <= playoff_teams)

            write_csv(out_dir / f"standings_{season}.csv", STANDING_FIELDS, rows)
            all_rows.extend(rows)
            cname = next((r["manager"] for r in rows if r["champion"]), "unknown")
            print(f"  standings/{season}: {len(rows)} teams (champion={cname})")
        except Exception as e:
            note_error(f"standings_{season}", e)

    write_csv(DATA_DIR / "league_history.csv", STANDING_FIELDS, all_rows)
    print(f"  league_history.csv: {len(all_rows)} rows")
    return all_rows


# ---------------------------------------------------------------------------
# 3. MATCHUPS
# ---------------------------------------------------------------------------
MATCHUP_FIELDS = [
    "season", "week", "roster_id", "manager", "team_name", "points",
    "opponent_roster_id", "opponent_manager", "opponent_points",
    "result", "is_playoff",
]


PLAYER_PTS_FIELDS = [
    "season", "player_id", "player_name", "position", "weeks_rostered",
    "points_regular", "points_total", "points_started", "weeks_started",
]


PW_FIELDS = [
    "season", "week", "roster_id", "user_id", "player_id", "player_name",
    "position", "points", "started", "is_playoff",
]


def pull_matchups(seasons, players):
    out_dir = DATA_DIR / "matchups"
    out_dir.mkdir(exist_ok=True)
    pts_dir = DATA_DIR / "player_points"
    pts_dir.mkdir(exist_ok=True)
    pw_dir = DATA_DIR / "player_weeks"
    pw_dir.mkdir(exist_ok=True)
    all_rows = []
    all_pts = []
    all_pw = []

    for league in seasons:
        season = league["season"]
        if league.get("status") not in ("complete", "in_season", "post_season"):
            print(f"  matchups/{season}: skipped (status={league.get('status')})")
            continue
        try:
            idx, _ = team_index(league["league_id"])
            settings = league.get("settings") or {}
            playoff_start = settings.get("playoff_week_start", 15)

            rows = []
            pw_rows = []
            # player_id -> [total_pts, weeks_rostered, started_pts,
            #               weeks_started, regular_season_pts]
            ptbook = {}
            for week in range(1, MAX_WEEK + 1):
                try:
                    ms = get(f"league/{league['league_id']}/matchups/{week}") or []
                except Exception as e:
                    note_error(f"matchups_{season}_week{week}", e)
                    continue
                if not ms:
                    continue

                # Weekly per-player scoring rides along in the matchup payload.
                # It is the only place Sleeper exposes actual fantasy production,
                # and it is what makes "was this keeper worth the pick" answerable.
                for m in ms:
                    starters = set(m.get("starters") or [])
                    t = idx.get(m["roster_id"], {})
                    for pid, pp in (m.get("players_points") or {}).items():
                        e = ptbook.setdefault(pid, [0.0, 0, 0.0, 0, 0.0])
                        e[0] += pp or 0
                        e[1] += 1
                        if pid in starters:
                            e[2] += pp or 0
                            e[3] += 1
                        # Sleeper returns player points for all 18 weeks,
                        # including fantasy playoff weeks and week 18 (which no
                        # matchup uses) and including eliminated teams. Keep the
                        # regular-season figure separate — it is the one that
                        # means "how good was this player for you this season".
                        if week < playoff_start:
                            e[4] += pp or 0
                        pw_rows.append({
                            "season": season,
                            "week": week,
                            "roster_id": m["roster_id"],
                            "user_id": t.get("user_id", ""),
                            "player_id": pid,
                            "player_name": player_name(players, pid),
                            "position": player_pos(players, pid),
                            "points": round(pp or 0, 2),
                            "started": int(pid in starters),
                            "is_playoff": int(week >= playoff_start),
                        })

                # Teams pair up by shared matchup_id. A null matchup_id means the
                # team is idle that week (eliminated / bye).
                by_mid = {}
                for m in ms:
                    if m.get("matchup_id") is None:
                        continue
                    by_mid.setdefault(m["matchup_id"], []).append(m)

                for pair in by_mid.values():
                    if len(pair) != 2:
                        continue
                    for a, b in ((pair[0], pair[1]), (pair[1], pair[0])):
                        ap = round(a.get("points") or 0, 2)
                        bp = round(b.get("points") or 0, 2)
                        ta = idx.get(a["roster_id"], {})
                        tb = idx.get(b["roster_id"], {})
                        rows.append({
                            "season": season,
                            "week": week,
                            "roster_id": a["roster_id"],
                            "manager": ta.get("manager", ""),
                            "team_name": ta.get("team_name", ""),
                            "points": ap,
                            "opponent_roster_id": b["roster_id"],
                            "opponent_manager": tb.get("manager", ""),
                            "opponent_points": bp,
                            "result": "W" if ap > bp else ("L" if ap < bp else "T"),
                            "is_playoff": week >= playoff_start,
                        })

            rows.sort(key=lambda r: (r["week"], r["roster_id"]))
            write_csv(out_dir / f"matchups_{season}.csv", MATCHUP_FIELDS, rows)
            all_rows.extend(rows)

            pw_rows.sort(key=lambda r: (r["week"], r["roster_id"], -r["points"]))
            write_csv(pw_dir / f"player_weeks_{season}.csv", PW_FIELDS, pw_rows)
            all_pw.extend(pw_rows)

            prows = [{
                "season": season,
                "player_id": pid,
                "player_name": player_name(players, pid),
                "position": player_pos(players, pid),
                "weeks_rostered": v[1],
                "points_regular": round(v[4], 2),
                "points_total": round(v[0], 2),
                "points_started": round(v[2], 2),
                "weeks_started": v[3],
            } for pid, v in ptbook.items()]
            prows.sort(key=lambda r: -r["points_total"])
            write_csv(pts_dir / f"player_points_{season}.csv", PLAYER_PTS_FIELDS, prows)
            all_pts.extend(prows)
            print(f"  matchups/{season}: {len(rows)} rows, {len(prows)} scored players")
        except Exception as e:
            note_error(f"matchups_{season}", e)

    write_csv(DATA_DIR / "matchups_all.csv", MATCHUP_FIELDS, all_rows)
    write_csv(DATA_DIR / "player_points_all.csv", PLAYER_PTS_FIELDS, all_pts)
    write_csv(DATA_DIR / "player_weeks_all.csv", PW_FIELDS, all_pw)
    print(f"  matchups_all.csv: {len(all_rows)} rows")
    print(f"  player_points_all.csv: {len(all_pts)} rows")
    print(f"  player_weeks_all.csv: {len(all_pw)} rows")
    return all_rows


# ---------------------------------------------------------------------------
# 3b. PLAYOFF BRACKETS
# ---------------------------------------------------------------------------
BRACKET_FIELDS = ["season", "bracket", "round", "matchup_id",
                  "roster_id_1", "roster_id_2", "winner", "loser", "position"]


def pull_brackets(seasons):
    out_dir = DATA_DIR / "brackets"
    out_dir.mkdir(exist_ok=True)
    all_rows = []
    for league in seasons:
        season = league["season"]
        if league.get("status") not in ("complete", "in_season", "post_season"):
            continue
        try:
            rows = []
            for name in ("winners_bracket", "losers_bracket"):
                for m in get(f"league/{league['league_id']}/{name}") or []:
                    # t1/t2/w/l can be dicts like {"w": 1} — placeholder
                    # references to earlier matchups — hence the guards.
                    rows.append({
                        "season": season, "bracket": name.split("_")[0],
                        "round": m.get("r"), "matchup_id": m.get("m"),
                        "roster_id_1": m.get("t1") if isinstance(m.get("t1"), int) else "",
                        "roster_id_2": m.get("t2") if isinstance(m.get("t2"), int) else "",
                        "winner": m.get("w") if isinstance(m.get("w"), int) else "",
                        "loser": m.get("l") if isinstance(m.get("l"), int) else "",
                        "position": m.get("p") or "",
                    })
            write_csv(out_dir / f"bracket_{season}.csv", BRACKET_FIELDS, rows)
            all_rows.extend(rows)
            print(f"  brackets/{season}: {len(rows)} rows")
        except Exception as e:
            note_error(f"bracket_{season}", e)
    write_csv(DATA_DIR / "brackets_all.csv", BRACKET_FIELDS, all_rows)
    print(f"  brackets_all.csv: {len(all_rows)} rows")


# ---------------------------------------------------------------------------
# 4. ROSTERS (end-of-season snapshot)
# ---------------------------------------------------------------------------
ROSTER_FIELDS = [
    "season", "roster_id", "manager", "team_name", "player_id",
    "player_name", "position", "nfl_team", "slot",
]


def pull_rosters(seasons, players):
    out_dir = DATA_DIR / "rosters"
    out_dir.mkdir(exist_ok=True)

    for league in seasons:
        season = league["season"]
        try:
            idx, rosters = team_index(league["league_id"])
            rows = []
            for r in rosters:
                rid = r["roster_id"]
                t = idx.get(rid, {})
                starters = set(r.get("starters") or [])
                reserve = set(r.get("reserve") or [])
                for pid in (r.get("players") or []):
                    slot = "starter" if pid in starters else ("ir" if pid in reserve else "bench")
                    rows.append({
                        "season": season,
                        "roster_id": rid,
                        "manager": t.get("manager", ""),
                        "team_name": t.get("team_name", ""),
                        "player_id": pid,
                        "player_name": player_name(players, pid),
                        "position": player_pos(players, pid),
                        "nfl_team": (players.get(str(pid)) or {}).get("team") or "",
                        "slot": slot,
                    })
            write_csv(out_dir / f"rosters_{season}.csv", ROSTER_FIELDS, rows)
            print(f"  rosters/{season}: {len(rows)} players")
        except Exception as e:
            note_error(f"rosters_{season}", e)


# ---------------------------------------------------------------------------
# 5. TRANSACTIONS
# ---------------------------------------------------------------------------
# The keeper rule penalises a player who was "dropped to waivers or traded at
# any point" — so add/drop history is rule-relevant data, not just trivia.
TX_FIELDS = [
    "season", "transaction_id", "week", "type", "status", "created_ms", "created_date",
    "roster_id", "manager", "action", "player_id", "player_name", "position",
    "faab_bid",
]


def pull_transactions(seasons, players):
    out_dir = DATA_DIR / "transactions"
    out_dir.mkdir(exist_ok=True)
    all_rows = []

    for league in seasons:
        season = league["season"]
        if league.get("status") not in ("complete", "in_season", "post_season"):
            print(f"  transactions/{season}: skipped (status={league.get('status')})")
            continue
        try:
            idx, _ = team_index(league["league_id"])
            rows = []
            for week in range(1, MAX_WEEK + 1):
                try:
                    txs = get(f"league/{league['league_id']}/transactions/{week}") or []
                except Exception as e:
                    note_error(f"transactions_{season}_week{week}", e)
                    continue

                for tx in txs:
                    faab = (tx.get("settings") or {}).get("waiver_bid", "")
                    # Sleeper tags offseason moves as leg 1, so `week` alone
                    # cannot distinguish a June drop from a week-1 drop. The
                    # created timestamp can.
                    cms = tx.get("created")
                    cdate = (time.strftime("%Y-%m-%d", time.localtime(cms / 1000))
                             if cms else "")
                    for action, mapping in (("add", tx.get("adds")), ("drop", tx.get("drops"))):
                        for pid, rid in (mapping or {}).items():
                            t = idx.get(rid, {})
                            rows.append({
                                "season": season,
                                "transaction_id": tx.get("transaction_id", ""),
                                "week": week,
                                "type": tx.get("type", ""),
                                "status": tx.get("status", ""),
                                "created_ms": cms or "",
                                "created_date": cdate,
                                "roster_id": rid,
                                "manager": t.get("manager", ""),
                                "action": action,
                                "player_id": pid,
                                "player_name": player_name(players, pid),
                                "position": player_pos(players, pid),
                                "faab_bid": faab if action == "add" else "",
                            })

            write_csv(out_dir / f"transactions_{season}.csv", TX_FIELDS, rows)
            all_rows.extend(rows)
            print(f"  transactions/{season}: {len(rows)} rows")
        except Exception as e:
            note_error(f"transactions_{season}", e)

    write_csv(DATA_DIR / "transactions_all.csv", TX_FIELDS, all_rows)
    print(f"  transactions_all.csv: {len(all_rows)} rows")
    return all_rows


# ---------------------------------------------------------------------------
# 6. MANAGERS (identity map across seasons)
# ---------------------------------------------------------------------------
def pull_managers(seasons):
    """
    roster_id is only stable within a season, and display names change. The
    user_id is the durable key, so emit a crosswalk for joins.
    """
    rows = []
    for league in seasons:
        idx, _ = team_index(league["league_id"])
        for rid, t in sorted(idx.items()):
            rows.append({
                "season": league["season"],
                "league_id": league["league_id"],
                "roster_id": rid,
                "user_id": t["user_id"],
                "manager": t["manager"],
                "team_name": t["team_name"],
                "avatar": t.get("avatar", ""),
            })
    write_csv(
        DATA_DIR / "managers.csv",
        ["season", "league_id", "roster_id", "user_id", "manager", "team_name", "avatar"],
        rows,
    )
    print(f"  managers.csv: {len(rows)} rows")
    return rows


# ---------------------------------------------------------------------------
# 7. LEAGUE SETTINGS SNAPSHOT
# ---------------------------------------------------------------------------
def pull_settings(seasons):
    rows = []
    for lg in seasons:
        s = lg.get("settings") or {}
        rows.append({
            "season": lg["season"],
            "league_id": lg["league_id"],
            "name": lg.get("name", ""),
            "status": lg.get("status", ""),
            "teams": lg.get("total_rosters", ""),
            "draft_id": lg.get("draft_id", ""),
            "previous_league_id": lg.get("previous_league_id", ""),
            "max_keepers": s.get("max_keepers", ""),
            "playoff_teams": s.get("playoff_teams", ""),
            "playoff_week_start": s.get("playoff_week_start", ""),
            "playoff_seed_type": s.get("playoff_seed_type", ""),
            "draft_start_ms": (lg.get("_draft_start") or ""),
            "draft_date": (time.strftime("%Y-%m-%d", time.localtime(lg["_draft_start"] / 1000))
                           if lg.get("_draft_start") else ""),
            "waiver_budget": s.get("waiver_budget", ""),
            "trade_deadline": s.get("trade_deadline", ""),
            "roster_positions": "|".join(lg.get("roster_positions") or []),
        })
    write_csv(
        DATA_DIR / "league_settings.csv",
        ["season", "league_id", "name", "status", "teams", "draft_id",
         "previous_league_id", "max_keepers", "playoff_teams",
         "playoff_week_start", "playoff_seed_type", "draft_start_ms",
         "draft_date", "waiver_budget", "trade_deadline", "roster_positions"],
        rows,
    )
    print(f"  league_settings.csv: {len(rows)} seasons")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"\nDiscovering Sleeper league history from {ROOT_LEAGUE_ID}...\n")
    DATA_DIR.mkdir(exist_ok=True)
    seasons = discover_seasons(ROOT_LEAGUE_ID)
    if not seasons:
        raise SystemExit("No leagues found — check ROOT_LEAGUE_ID.")
    print("  seasons: " + ", ".join(
        f"{lg['season']}({lg['total_rosters']}tm,{lg['status']})" for lg in seasons))

    players = load_players()

    print("\n=== MANAGERS ===")
    pull_managers(seasons)

    # Drafts first: it stashes each season's draft start time, which the
    # settings snapshot reports and the analysis uses to tell an offseason
    # move from an in-season one.
    print("\n=== DRAFTS ===")
    draft_rows = pull_drafts(seasons, players)

    print("\n=== SETTINGS ===")
    pull_settings(seasons)

    print("\n=== STANDINGS ===")
    pull_standings(seasons, draft_rows)

    print("\n=== MATCHUPS ===")
    pull_matchups(seasons, players)

    print("\n=== BRACKETS ===")
    pull_brackets(seasons)

    print("\n=== ROSTERS ===")
    pull_rosters(seasons, players)

    print("\n=== TRANSACTIONS ===")
    pull_transactions(seasons, players)

    print(f"\n{'='*55}")
    if errors:
        print(f"Completed with {len(errors)} skipped items:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("All data pulled successfully.")
