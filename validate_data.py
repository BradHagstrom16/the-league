#!/usr/bin/env python3
"""Pipeline invariants. Run after pull, before build. Exit 1 on any failure."""
import csv, sys
from collections import defaultdict
from pathlib import Path


def _read(p):
    with open(p) as f:
        return list(csv.DictReader(f))


def check_standings_reconcile(base):
    """Standings wins/losses and points_for reconcile with regular-season matchup rows."""
    fails = []
    for st_file in sorted((base / "standings").glob("standings_*.csv")):
        season = st_file.stem.split("_")[1]
        st = _read(st_file)
        if not any(r["finish"] for r in st):
            continue  # unplayed season
        mu = [r for r in _read(base / "matchups" / f"matchups_{season}.csv")
              if r["is_playoff"] == "False"]
        wins, losses, pf = defaultdict(int), defaultdict(int), defaultdict(float)
        for r in mu:
            rid = r["roster_id"]
            pf[rid] += float(r["points"])
            if r["result"] == "W":
                wins[rid] += 1
            elif r["result"] == "L":
                losses[rid] += 1
        for r in st:
            rid = r["roster_id"]
            if int(r["wins"]) != wins[rid]:
                fails.append(f"{season} roster {rid}: standings wins {r['wins']} != matchup wins {wins[rid]}")
            if int(r["losses"]) != losses[rid]:
                fails.append(f"{season} roster {rid}: standings losses {r['losses']} != matchup losses {losses[rid]}")
            if abs(float(r["points_for"]) - pf[rid]) > 0.02:
                fails.append(f"{season} roster {rid}: PF mismatch {r['points_for']} vs {round(pf[rid], 2)}")
    return fails


def check_matchup_pairing(base):
    """Every matchup row has a mirror row (A-vs-B and B-vs-A) with cross-matching points."""
    fails = []
    for mu_file in sorted((base / "matchups").glob("matchups_*.csv")):
        season = mu_file.stem.split("_")[1]
        by_week = defaultdict(list)
        for r in _read(mu_file):
            by_week[r["week"]].append(r)
        for week, rows in by_week.items():
            lookup = {(r["roster_id"], r["opponent_roster_id"]): r for r in rows}
            seen = set()
            for r in rows:
                pair_key = frozenset((r["roster_id"], r["opponent_roster_id"]))
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                mirror = lookup.get((r["opponent_roster_id"], r["roster_id"]))
                if mirror is None:
                    fails.append(f"{season} week {week}: roster {r['roster_id']} vs {r['opponent_roster_id']} has no mirror row")
                    continue
                if abs(float(r["points"]) - float(mirror["opponent_points"])) > 0.02 or \
                   abs(float(r["opponent_points"]) - float(mirror["points"])) > 0.02:
                    fails.append(
                        f"{season} week {week}: roster {r['roster_id']} vs {r['opponent_roster_id']} "
                        f"points cross-match mismatch ({r['points']}/{r['opponent_points']} vs "
                        f"{mirror['points']}/{mirror['opponent_points']})"
                    )
    return fails


def check_manager_crosswalk(base):
    """Every (season, roster_id) referenced in standings has a non-empty user_id in managers.csv."""
    fails = []
    mgr_map = {(r["season"], r["roster_id"]): r["user_id"] for r in _read(base / "managers.csv")}
    for st_file in sorted((base / "standings").glob("standings_*.csv")):
        season = st_file.stem.split("_")[1]
        for r in _read(st_file):
            key = (season, r["roster_id"])
            uid = mgr_map.get(key)
            if uid is None:
                fails.append(f"{season} roster {r['roster_id']}: not found in managers.csv")
            elif not uid:
                fails.append(f"{season} roster {r['roster_id']}: empty user_id in managers.csv")
    return fails


def check_starter_sums(base):
    """Sum of started player_weeks points equals the matchup points for that (season, week, roster_id)."""
    fails = []
    for pw_file in sorted((base / "player_weeks").glob("player_weeks_*.csv")):
        season = pw_file.stem.split("_")[1]
        mu_path = base / "matchups" / f"matchups_{season}.csv"
        if not mu_path.exists():
            continue  # unplayed season
        mu_lookup = {(r["week"], r["roster_id"]): r for r in _read(mu_path)}

        sums = defaultdict(float)
        is_playoff = {}
        for r in _read(pw_file):
            key = (r["week"], r["roster_id"])
            if r["started"] == "1":
                sums[key] += float(r["points"])
            is_playoff[key] = r["is_playoff"]

        for key, total in sums.items():
            week, rid = key
            mrow = mu_lookup.get(key)
            if mrow is None:
                continue  # idle week (bye/eliminated) - no matchup row to compare
            if (is_playoff[key] == "1") != (mrow["is_playoff"] == "True"):
                continue  # playoff-flag mismatch - not comparable, skip
            if abs(total - float(mrow["points"])) > 0.02:
                fails.append(
                    f"{season} week {week} roster {rid}: starter sum {round(total, 2)} "
                    f"!= matchup points {mrow['points']}"
                )
    return fails


def check_champion(base):
    """Each complete season has exactly one champion, matching the winners-bracket position==1 winner."""
    fails = []
    for st_file in sorted((base / "standings").glob("standings_*.csv")):
        season = st_file.stem.split("_")[1]
        st = _read(st_file)
        if not any(r["finish"] for r in st):
            continue  # unplayed season
        champs = [r for r in st if r["champion"] == "1"]
        if len(champs) != 1:
            fails.append(f"{season}: expected exactly one champion==1 row, found {len(champs)}")
            continue
        champ_rid = champs[0]["roster_id"]

        bracket_path = base / "brackets" / f"bracket_{season}.csv"
        if not bracket_path.exists():
            fails.append(f"{season}: no bracket file to verify champion against")
            continue
        finals = [r for r in _read(bracket_path) if r["bracket"] == "winners" and r["position"] == "1"]
        if len(finals) != 1:
            fails.append(f"{season}: expected exactly one winners-bracket position==1 row, found {len(finals)}")
            continue
        bracket_champ_rid = finals[0]["winner"]

        if champ_rid != bracket_champ_rid:
            fails.append(f"{season}: standings champion roster {champ_rid} != bracket winner roster {bracket_champ_rid}")
    return fails


def check_no_finish_for_unplayed(base):
    """Seasons with status pre_draft/drafting must have empty finish for every roster."""
    fails = []
    for r in _read(base / "league_settings.csv"):
        if r["status"] in ("pre_draft", "drafting"):
            season = r["season"]
            st_path = base / "standings" / f"standings_{season}.csv"
            if not st_path.exists():
                continue
            for row in _read(st_path):
                if row["finish"]:
                    fails.append(
                        f"{season} roster {row['roster_id']}: has finish {row['finish']!r} "
                        f"but season status is {r['status']!r}"
                    )
    return fails


def check_aggregates(base):
    """Each aggregate CSV's row count equals the sum of its per-season files."""
    fails = []
    pairs = [
        ("matchups_all.csv", "matchups/matchups_*.csv"),
        ("player_weeks_all.csv", "player_weeks/player_weeks_*.csv"),
        ("transactions_all.csv", "transactions/transactions_*.csv"),
        ("drafts_all.csv", "drafts/draft_*.csv"),
        ("league_history.csv", "standings/standings_*.csv"),
        ("brackets_all.csv", "brackets/bracket_*.csv"),
    ]
    for agg_name, pattern in pairs:
        agg_path = base / agg_name
        if not agg_path.exists():
            fails.append(f"{agg_name}: aggregate file missing")
            continue
        agg_count = len(_read(agg_path))
        part_count = sum(len(_read(p)) for p in sorted(base.glob(pattern)))
        if agg_count != part_count:
            fails.append(
                f"{agg_name}: aggregate row count {agg_count} != sum of per-season files {part_count}"
            )
    return fails


def run_checks(base):
    fails = []
    fails += check_standings_reconcile(base)
    fails += check_matchup_pairing(base)
    fails += check_manager_crosswalk(base)
    fails += check_starter_sums(base)
    fails += check_champion(base)
    fails += check_no_finish_for_unplayed(base)
    fails += check_aggregates(base)
    return fails


if __name__ == "__main__":
    base = Path(__file__).parent / "data"
    failures = run_checks(base)
    for f in failures:
        print(f)
    sys.exit(1 if failures else 0)
