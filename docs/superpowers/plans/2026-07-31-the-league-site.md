# "The League" Stats Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public, auto-updating GitHub Pages stats site for Sleeper league `1315570882550202368` ("The league"), covering all six seasons (2021–2026), exceeding the ggg-league baseline in stats depth and presentation.

**Architecture:** Python pipeline → committed CSVs (`data/`) → computed stats as JSON (`site/data/`) + Jinja2-rendered static HTML (`site/`). No Node toolchain; charts are Python-generated inline SVG; interactivity is small vanilla JS. A GitHub Action refreshes weekly in season.

**Tech Stack:** Python 3.9+ stdlib (puller), pandas + jinja2 + pyyaml (builder), pytest (tests), GitHub Actions + Pages (hosting).

**Working directory:** `/Users/bhagstrom/FootballFantasy/the-league` (git repo already initialized, spec committed). The baseline repo to adapt from is checked out at `/Users/bhagstrom/FootballFantasy/ggg-league` — read its files when a task says "adapt from baseline".

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-31-the-league-site-design.md`. Read it before starting.
- `ROOT_LEAGUE_ID = "1315570882550202368"` — the only per-season constant.
- Seasons discovered by walking `previous_league_id`: 2021–2024 are 10-team, 2025–2026 are 12-team. Era-sensitive stats must be annotated (see Task 3 `era` column).
- `pull_league_data.py` uses ONLY the Python standard library.
- Baseline gotchas are law: filter transactions to `status == "complete"` for adds/drops; use `slot_owner_roster_id` for draft-slot analysis; use regular-season points (weeks `< playoff_week_start`), never all-18-week totals; join on `user_id` never display name; `finish` = wins desc, then points-for desc.
- 2026 is `pre_draft`: it appears in settings/managers/keeper-declarations but NEVER in matchup, standings-with-finish, or record computations. Every stats module must tolerate its presence in the CSVs.
- The site must build even if `manager_names.csv` real names are blank (fall back to Sleeper handle) and if `league_lore.yml` is empty (lore sections render a "fill me in" placeholder).
- No external site dependencies: no CDN links, no web fonts, no JS libraries. Everything served from `site/`.
- All commits: end message with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Design authority: `PRODUCT.md` (impeccable product record, at repo root) is durable product truth; Task 13's new-work flow establishes `DESIGN.md` (the visual world). Later tasks refine within that world — never fork a second aesthetic.
- Python venv lives at `.venv/`; every Run command below assumes `source .venv/bin/activate` (Task 1 creates it).

## File Structure (final state)

```
pull_league_data.py            Sleeper API → data/*.csv (stdlib only)
validate_data.py               pipeline invariants; non-zero exit on failure
build_site.py                  orchestrator: load → compute → JSON + HTML
run.sh                         venv bootstrap; pull → validate → build
requirements.txt               pandas, jinja2, pyyaml, pytest
manager_names.csv              HAND-MAINTAINED handle → first name (template generated)
league_lore.yml                HAND-MAINTAINED trophy/punishment lore (template generated)
data/                          per-season CSVs + *_all.csv (Task 1)
leaguestats/
  __init__.py
  loading.py                   LeagueData dataclass + load_data()
  career.py                    compute_career()
  headtohead.py                compute_h2h()
  luck.py                      compute_luck(), allplay_week()
  lineups.py                   compute_lineups(), optimal_points()
  draftstats.py                compute_drafts(), surplus tables
  keepers.py                   compute_keepers(), audit_keepers(), left_roster()
  txstats.py                   compute_transactions(), faab_ledger(), trade_ledger()
  recordbook.py                compute_records()
  charts.py                    svg_line(), svg_bar(), svg_heatmap()
  render.py                    Jinja2 env + render_page()
templates/                     Jinja2 templates (base + one per page type)
site/                          generated HTML + assets/ + data/*.json  (committed)
site/assets/css/style.css      design system (hand-written, not generated)
site/assets/js/tables.js       sortable tables (hand-written)
tests/
  conftest.py                  tiny synthetic 4-team league fixture
  test_validation.py … test_recordbook.py   per-module tests
.github/workflows/update.yml   weekly cron + manual dispatch → pull, build, commit, deploy
```

**Interface rule used throughout:** every stats module exposes one entry point `compute_<name>(data: LeagueData) -> dict` returning a JSON-serializable dict. `build_site.py` calls each, writes `site/data/<name>.json`, and passes the same dicts to templates. Tests import the module functions directly.

---

### Task 1: Scaffolding + data puller (adapt from baseline)

**Files:**
- Create: `pull_league_data.py`, `run.sh`, `requirements.txt`, `.gitignore`, `data/` (generated CSVs)

**Interfaces:**
- Consumes: Sleeper API; baseline `/Users/bhagstrom/FootballFantasy/ggg-league/pull_league_data.py`
- Produces: `data/{drafts,standings,matchups,rosters,transactions,player_points,player_weeks,brackets}/*_{season}.csv`, `data/*_all.csv`, `data/managers.csv`, `data/league_settings.csv`. Column contracts listed below — Tasks 2–3 depend on them exactly.

The baseline puller is proven code that already handles every API gotcha. Copy it and make the specific changes below — do not rewrite it from scratch. This task has no pytest cycle (it is network IO); its verification is the live smoke run in Step 4 plus Task 2's invariants. That is a deliberate exception to TDD, contained to this task.

- [ ] **Step 1: Scaffolding**

`.gitignore`:
```
.venv/
.cache/
__pycache__/
*.pyc
.pytest_cache/
```

`requirements.txt`:
```
pandas>=1.5
jinja2>=3.0
pyyaml>=6.0
pytest>=7.0
```

`run.sh` (mode flags let the Action and local dev share one entry point):
```bash
#!/usr/bin/env bash
# Pull fresh data from Sleeper, validate it, rebuild the site.
#   ./run.sh            pull + validate + build
#   ./run.sh --build    validate + build only, no network
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
fi
if [ "${1:-}" != "--build" ]; then
  .venv/bin/python pull_league_data.py
fi
.venv/bin/python validate_data.py
.venv/bin/python build_site.py
```
Run `chmod +x run.sh`. Create the venv now: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.

- [ ] **Step 2: Copy and adapt the puller**

`cp /Users/bhagstrom/FootballFantasy/ggg-league/pull_league_data.py pull_league_data.py`, then make exactly these changes:

1. **Constants and docstring.** `ROOT_LEAGUE_ID = "1315570882550202368"`. Rewrite the module docstring for "The league" (drop the GGG references and the warning comment about this league — we ARE this league now). Add `DATA_DIR = BASE_DIR / "data"` and replace every output path that used `BASE_DIR` with `DATA_DIR` (subdirs `data/drafts/`, `data/standings/`, etc.; `*_all.csv`, `managers.csv`, `league_settings.csv` go directly in `data/`). `DATA_DIR.mkdir(exist_ok=True)` in main. `.cache/` stays at repo root.

2. **Transactions: add `transaction_id`.** In `TX_FIELDS` insert `"transaction_id"` after `"season"`; in the row dict add `"transaction_id": tx.get("transaction_id", "")`. Task 10's trade ledger groups on this.

3. **Player weeks (new output, needed by lineups/trades/FAAB).** Inside `pull_matchups`'s week loop, alongside the existing `ptbook` aggregation, collect per-row player weeks. Add at function top: `pw_dir = DATA_DIR / "player_weeks"; pw_dir.mkdir(exist_ok=True); all_pw = []` and per season `pw_rows = []`. Inside the `for m in ms:` loop that walks `players_points`:

```python
for m in ms:
    starters = set(m.get("starters") or [])
    t = idx.get(m["roster_id"], {})
    for pid, pp in (m.get("players_points") or {}).items():
        pw_rows.append({
            "season": season, "week": week,
            "roster_id": m["roster_id"],
            "user_id": t.get("user_id", ""),
            "player_id": pid,
            "player_name": player_name(players, pid),
            "position": player_pos(players, pid),
            "points": round(pp or 0, 2),
            "started": int(pid in starters),
            "is_playoff": int(week >= playoff_start),
        })
```
(Merge this with the existing `ptbook` loop — one pass, both outputs.) After the week loop: `write_csv(pw_dir / f"player_weeks_{season}.csv", PW_FIELDS, pw_rows)` and extend `all_pw`; after the season loop write `data/player_weeks_all.csv`. `PW_FIELDS = ["season","week","roster_id","user_id","player_id","player_name","position","points","started","is_playoff"]`.

4. **Brackets (new output).** Add a `pull_brackets(seasons)` function and call it from main after standings:

```python
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
```
(`t1`/`t2` can be dicts like `{"w": 1}` — placeholder references to earlier matchups — hence the `isinstance` guards.)

5. **Settings snapshot: add `total_rosters` already exists as `teams`; also append `"playoff_seed_type"` from settings** (used to explain bracket reseeding on season pages): add `"playoff_seed_type": s.get("playoff_seed_type", "")` to the row and field list in `pull_settings`.

- [ ] **Step 3: Run the puller live**

Run: `.venv/bin/python pull_league_data.py`
Expected output: seasons line reading `2021(10tm,complete), 2022(10tm,complete), 2023(10tm,complete), 2024(10tm,complete), 2025(12tm,complete), 2026(12tm,pre_draft)`; drafts for 2021–2025 (2026 may report "no picks (draft not started)" — that is fine); matchups/player_weeks/brackets/transactions for 2021–2025; zero hard errors. If `draft_2026` yields picks (keepers declared in Sleeper), that is also fine.

- [ ] **Step 4: Sanity-check the CSVs**

Run: `python3 - <<'EOF'`
```python
import csv, pathlib
d = pathlib.Path("data")
hist = list(csv.DictReader(open(d/"league_history.csv")))
assert len([r for r in hist if r["finish"]]) == 4*10 + 12, "played standings rows"
mw = list(csv.DictReader(open(d/"matchups_all.csv")))
assert {r["season"] for r in mw} == {"2021","2022","2023","2024","2025"}
pw = list(csv.DictReader(open(d/"player_weeks_all.csv")))
assert len(pw) > 10000 and {"started","points","user_id"} <= set(pw[0])
tx = list(csv.DictReader(open(d/"transactions_all.csv")))
assert any(r["transaction_id"] for r in tx)
br = list(csv.DictReader(open(d/"brackets_all.csv")))
assert {r["season"] for r in br} == {"2021","2022","2023","2024","2025"}
print("OK", len(hist), len(mw), len(pw), len(tx), len(br))
EOF
```
Expected: `OK` with counts. Fix the puller if any assert fires.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: data puller adapted from ggg-league baseline + player_weeks/brackets

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Pipeline validation (`validate_data.py`)

**Files:**
- Create: `validate_data.py`, `tests/test_validation.py`

**Interfaces:**
- Consumes: `data/*.csv` from Task 1 (real committed data is the test fixture)
- Produces: `validate_data.py` with `run_checks(base: Path) -> list[str]` (returns list of failure strings, empty = pass) and a `__main__` that prints failures and exits 1 if any. `run.sh` already calls it.

Invariants (each is one small function returning `list[str]`, all called by `run_checks`):

1. `check_standings_reconcile`: for every complete season, wins/losses and points-for in `standings_{s}.csv` equal the W/L count and points sum recomputed from regular-season rows of `matchups_{s}.csv` (points to 2dp tolerance 0.02).
2. `check_matchup_pairing`: in every season/week, each `matchup_id` group referenced has its mirror row (A vs B and B vs A) and `points`/`opponent_points` cross-match.
3. `check_manager_crosswalk`: every `(season, roster_id)` in standings appears in `managers.csv` with a non-empty `user_id`.
4. `check_starter_sums`: for every complete season, per (season, week, roster_id): sum of `player_weeks` rows with `started == 1` equals matchup `points` within 0.02 (skip zero-point idle weeks where a roster has no matchup row).
5. `check_champion`: each complete season has exactly one `champion == 1` row in standings and it matches the `winner` of the `position == 1` winners-bracket row via roster_id.
6. `check_no_finish_for_unplayed`: seasons with status `pre_draft`/`drafting` have empty `finish` in standings (2026 must not rank).

- [ ] **Step 1: Write the failing tests**

`tests/test_validation.py`:
```python
from pathlib import Path
import validate_data as v

BASE = Path(__file__).resolve().parent.parent / "data"

def test_all_invariants_pass_on_committed_data():
    failures = v.run_checks(BASE)
    assert failures == []

def test_reconcile_catches_corruption(tmp_path):
    import shutil, csv
    shutil.copytree(BASE, tmp_path / "data")
    p = tmp_path / "data" / "standings" / "standings_2025.csv"
    rows = list(csv.DictReader(open(p)))
    rows[0]["wins"] = str(int(rows[0]["wins"]) + 1)
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    assert v.run_checks(tmp_path / "data") != []
```

- [ ] **Step 2: Run tests to verify they fail** — `pytest tests/test_validation.py -v` → FAIL (`No module named validate_data`).

- [ ] **Step 3: Implement `validate_data.py`** — stdlib csv only (it runs before pandas is guaranteed). Skeleton:

```python
#!/usr/bin/env python3
"""Pipeline invariants. Run after pull, before build. Exit 1 on any failure."""
import csv, sys
from collections import defaultdict
from pathlib import Path

def _read(p):
    with open(p) as f:
        return list(csv.DictReader(f))

def check_standings_reconcile(base):
    fails = []
    for st_file in sorted((base / "standings").glob("standings_*.csv")):
        season = st_file.stem.split("_")[1]
        st = _read(st_file)
        if not any(r["finish"] for r in st):
            continue  # unplayed season
        mu = [r for r in _read(base / "matchups" / f"matchups_{season}.csv")
              if r["is_playoff"] == "False"]
        wins, pf = defaultdict(int), defaultdict(float)
        for r in mu:
            rid = r["roster_id"]
            pf[rid] += float(r["points"])
            if r["result"] == "W":
                wins[rid] += 1
        for r in st:
            rid = r["roster_id"]
            if int(r["wins"]) != wins[rid]:
                fails.append(f"{season} roster {rid}: standings wins {r['wins']} != matchup wins {wins[rid]}")
            if abs(float(r["points_for"]) - pf[rid]) > 0.02:
                fails.append(f"{season} roster {rid}: PF mismatch {r['points_for']} vs {round(pf[rid],2)}")
    return fails
```
Implement the other five checks in the same shape. `run_checks(base)` concatenates all six. `__main__`: run against `Path(__file__).parent / "data"`, print each failure, `sys.exit(1 if failures else 0)`.

Note on check 4: build the matchup points lookup first and only compare where a matchup row exists; also skip rows where `is_playoff` differs. Note on check 1: `is_playoff` is serialized by the stdlib csv writer as the strings `True`/`False` — compare strings, and keep that quirk in mind everywhere CSVs are read without pandas.

- [ ] **Step 4: Run tests** — `pytest tests/test_validation.py -v` → both PASS. Also run `.venv/bin/python validate_data.py` → exit 0. If a real invariant fails here, the bug is in the puller — fix it there (this is the point of the task), re-pull, re-commit data.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: pipeline validation invariants ..."` (trailer as per Global Constraints).

---

### Task 3: `leaguestats` package, LeagueData loader, hand-maintained templates

**Files:**
- Create: `leaguestats/__init__.py` (empty), `leaguestats/loading.py`, `tests/conftest.py`, `tests/test_loading.py`, `manager_names.csv`, `league_lore.yml`, `pytest.ini`

**Interfaces:**
- Consumes: `data/*.csv` (Task 1 contracts)
- Produces (everything later tasks import):
  - `loading.LeagueData` dataclass, fields all `pd.DataFrame` unless noted: `matchups, drafts, standings, player_weeks, player_points, transactions, managers, settings, brackets`; plus `names: dict[str,str]` (user_id → preferred name), `handles: dict[str,str]` (user_id → latest Sleeper handle), `avatars: dict[str,str]` (user_id → Sleeper avatar id or ""), `lore: dict`.
  - Methods: `reg_matchups() -> pd.DataFrame` (played regular-season rows, numeric season/week/points, plus `user_id` and `opponent_user_id` columns merged on); `r2u(season:int) -> dict[int,str]`; `display(user_id:str) -> str`; `era(season:int) -> str` ("10-team" if season <= 2024 else "12-team"); `played_seasons() -> list[int]` (complete seasons only, from settings `status`).
  - `load_data(base: Path) -> LeagueData` where `base` is the repo root (reads `base/'data'`, `base/'manager_names.csv'`, `base/'league_lore.yml'`).
  - `write_name_template(base: Path)` — creates/updates `manager_names.csv` with all distinct user_ids across history: columns `user_id,handle,real_name` (real_name blank if new). Never overwrites filled-in real names.

`pytest.ini`:
```ini
[pytest]
testpaths = tests
```

- [ ] **Step 1: Write the shared synthetic fixture** — `tests/conftest.py`. This tiny hand-computed league is the fixture for Tasks 4–11, so every expected value in later tests derives from it. 4 teams (user ids `u1..u4`, roster ids 1–4, names Al/Bo/Cy/Di), one complete season `2024` with 3 regular weeks + 1 playoff week, `playoff_week_start=4`, roster slots `QB,RB,FLEX,SUPER_FLEX,BN,BN`:

```python
import pandas as pd
import pytest
from leaguestats.loading import LeagueData

# Weekly team scores (weeks 1-3 regular, week 4 playoff final: r1 vs r2).
# w1: r1 110 beats r2 100; r3 90 beats r4 80
# w2: r1 105 loses to r3 120; r2 95 beats r4 85
# w3: r1 130 beats r4 70;  r2 100 loses to r3 101
# Regular season: r3 3-0, r1 2-1, r2 1-2, r4 0-3
# w4 playoff: r1 100 beats r3 90  -> champion u1
_SCHED = [
    (1, 1, 110, 2, 100, False), (1, 3, 90, 4, 80, False),
    (2, 1, 105, 3, 120, False), (2, 2, 95, 4, 85, False),
    (3, 1, 130, 4, 70, False), (3, 2, 100, 3, 101, False),
    (4, 1, 100, 3, 90, True),
]

def _matchups():
    rows = []
    for wk, ra, pa, rb, pb, po in _SCHED:
        for (r1, p1, r2, p2) in ((ra, pa, rb, pb), (rb, pb, ra, pa)):
            rows.append(dict(season=2024, week=wk, roster_id=r1, points=p1,
                             opponent_roster_id=r2, opponent_points=p2,
                             result="W" if p1 > p2 else "L", is_playoff=po,
                             manager=f"h{r1}", team_name=f"T{r1}",
                             opponent_manager=f"h{r2}"))
    return pd.DataFrame(rows)

@pytest.fixture
def tiny() -> LeagueData:
    managers = pd.DataFrame([
        dict(season=2024, league_id="L1", roster_id=r, user_id=f"u{r}",
             manager=f"h{r}", team_name=f"T{r}") for r in (1, 2, 3, 4)])
    standings = pd.DataFrame([
        dict(season=2024, roster_id=3, user_id="u3", manager="h3", wins=3, losses=0,
             ties=0, points_for=311.0, points_against=285.0, finish=1, champion=0,
             made_playoffs=1, draft_slot=3, waiver_budget_used=50, total_moves=5),
        dict(season=2024, roster_id=1, user_id="u1", manager="h1", wins=2, losses=1,
             ties=0, points_for=345.0, points_against=290.0, finish=2, champion=1,
             made_playoffs=1, draft_slot=1, waiver_budget_used=100, total_moves=9),
        dict(season=2024, roster_id=2, user_id="u2", manager="h2", wins=1, losses=2,
             ties=0, points_for=295.0, points_against=296.0, finish=3, champion=0,
             made_playoffs=0, draft_slot=2, waiver_budget_used=0, total_moves=1),
        dict(season=2024, roster_id=4, user_id="u4", manager="h4", wins=0, losses=3,
             ties=0, points_for=235.0, points_against=315.0, finish=4, champion=0,
             made_playoffs=0, draft_slot=4, waiver_budget_used=125, total_moves=3),
    ])
    # Draft: 3 rounds, 4 slots, snake irrelevant here. One keeper (u1 keeps QB_A at rd 3).
    drafts = pd.DataFrame([
        dict(season=2024, round=rd, overall_pick=(rd - 1) * 4 + s, draft_slot=s,
             slot_owner_roster_id=s, roster_id=s, traded_pick=0, user_id=f"u{s}",
             manager=f"h{s}", player_id=f"P{rd}{s}", player_name=f"P{rd}{s}",
             position=pos, is_keeper=(rd == 3 and s == 1))
        for rd, pos in ((1, "QB"), (2, "RB"), (3, "WR"))
        for s in (1, 2, 3, 4)])
    # Player weeks: only roster 1 detailed (enough for lineup tests); others empty.
    player_weeks = pd.DataFrame([
        # week 1, roster 1: starters QB 30, RB 20, WR(FLEX) 25, QB2(SF) 35 = 110
        dict(season=2024, week=1, roster_id=1, user_id="u1", player_id="QB_A",
             player_name="QB_A", position="QB", points=30.0, started=1, is_playoff=0),
        dict(season=2024, week=1, roster_id=1, user_id="u1", player_id="RB_A",
             player_name="RB_A", position="RB", points=20.0, started=1, is_playoff=0),
        dict(season=2024, week=1, roster_id=1, user_id="u1", player_id="WR_A",
             player_name="WR_A", position="WR", points=25.0, started=1, is_playoff=0),
        dict(season=2024, week=1, roster_id=1, user_id="u1", player_id="QB_B",
             player_name="QB_B", position="QB", points=35.0, started=1, is_playoff=0),
        # bench: RB_B 28 (should have started over RB_A -> optimal 118)
        dict(season=2024, week=1, roster_id=1, user_id="u1", player_id="RB_B",
             player_name="RB_B", position="RB", points=28.0, started=0, is_playoff=0),
        dict(season=2024, week=1, roster_id=1, user_id="u1", player_id="WR_B",
             player_name="WR_B", position="WR", points=10.0, started=0, is_playoff=0),
    ])
    transactions = pd.DataFrame([
        # completed FAAB add: u2 buys WAIV_1 for $30 in week 2
        dict(season=2024, transaction_id="t1", week=2, type="waiver", status="complete",
             created_ms=1000, created_date="2024-09-18", roster_id=2, manager="h2",
             action="add", player_id="WAIV_1", player_name="WAIV_1", position="RB",
             faab_bid=30),
        # failed claim on the same player by u4 (must be ignored everywhere)
        dict(season=2024, transaction_id="t2", week=2, type="waiver", status="failed",
             created_ms=1000, created_date="2024-09-18", roster_id=4, manager="h4",
             action="add", player_id="WAIV_1", player_name="WAIV_1", position="RB",
             faab_bid=45),
        # trade t3 week 2: u1 sends RB_A to u3 for WR_C
        dict(season=2024, transaction_id="t3", week=2, type="trade", status="complete",
             created_ms=2000, created_date="2024-09-19", roster_id=3, manager="h3",
             action="add", player_id="RB_A", player_name="RB_A", position="RB", faab_bid=""),
        dict(season=2024, transaction_id="t3", week=2, type="trade", status="complete",
             created_ms=2000, created_date="2024-09-19", roster_id=1, manager="h1",
             action="add", player_id="WR_C", player_name="WR_C", position="WR", faab_bid=""),
        dict(season=2024, transaction_id="t3", week=2, type="trade", status="complete",
             created_ms=2000, created_date="2024-09-19", roster_id=1, manager="h1",
             action="drop", player_id="RB_A", player_name="RB_A", position="RB", faab_bid=""),
        dict(season=2024, transaction_id="t3", week=2, type="trade", status="complete",
             created_ms=2000, created_date="2024-09-19", roster_id=3, manager="h3",
             action="drop", player_id="WR_C", player_name="WR_C", position="WR", faab_bid=""),
    ])
    settings = pd.DataFrame([dict(
        season=2024, league_id="L1", name="Tiny", status="complete", teams=4,
        draft_id="D1", previous_league_id="", max_keepers=2, playoff_teams=2,
        playoff_week_start=4, draft_start_ms=100, draft_date="2024-08-25",
        waiver_budget=125, trade_deadline=13, playoff_seed_type=0,
        roster_positions="QB|RB|FLEX|SUPER_FLEX|BN|BN")])
    brackets = pd.DataFrame([dict(season=2024, bracket="winners", round=1, matchup_id=1,
                                  roster_id_1=1, roster_id_2=3, winner=1, loser=3,
                                  position=1)])
    # Season totals per drafted player. Round averages: r1 157.5, r2 90, r3 45.
    _pts = {"P11": 200, "P12": 180, "P13": 150, "P14": 100,
            "P21": 120, "P22": 110, "P23": 90, "P24": 40,
            "P31": 80, "P32": 30, "P33": 60, "P34": 10}
    player_points = pd.DataFrame([
        dict(season=2024, player_id=pid, player_name=pid,
             position={"1": "QB", "2": "RB", "3": "WR"}[pid[1]],
             weeks_rostered=14, points_regular=float(v), points_total=float(v) + 5,
             points_started=float(v), weeks_started=13)
        for pid, v in _pts.items()])
    return LeagueData(
        matchups=_matchups(), drafts=drafts, standings=standings,
        player_weeks=player_weeks, player_points=player_points,
        transactions=transactions, settings=settings,
        managers=managers, brackets=brackets,
        names={"u1": "Al", "u2": "Bo", "u3": "Cy", "u4": "Di"},
        handles={f"u{r}": f"h{r}" for r in (1, 2, 3, 4)},
        avatars={}, lore={"trophy_name": "The Tiny Cup",
                          "punishments": {2024: "Di waxed his legs"}})
```

Post-trade player_weeks note: after week 2 the fixture intentionally keeps things minimal; Task 10's tests add the few extra rows they need via a helper, not by editing this fixture.

- [ ] **Step 2: Write failing loader tests** — `tests/test_loading.py`:

```python
from pathlib import Path
import pandas as pd
from leaguestats.loading import LeagueData, load_data, write_name_template

BASE = Path(__file__).resolve().parent.parent

def test_load_real_data():
    d = load_data(BASE)
    assert set(d.played_seasons()) == {2021, 2022, 2023, 2024, 2025}
    assert d.era(2024) == "10-team" and d.era(2025) == "12-team"
    reg = d.reg_matchups()
    assert reg.is_playoff.eq(False).all()
    assert {"user_id", "opponent_user_id"} <= set(reg.columns)
    assert reg[reg.season == 2025].roster_id.nunique() == 12

def test_display_falls_back_to_handle(tiny):
    tiny.names.pop("u2")
    assert tiny.display("u2") == "h2"
    assert tiny.display("u1") == "Al"

def test_name_template_preserves_filled_names(tmp_path):
    import csv, shutil
    shutil.copytree(BASE / "data", tmp_path / "data")
    (tmp_path / "manager_names.csv").write_text(
        "user_id,handle,real_name\n735974647736213504,KingTowsk,Brad\n")
    write_name_template(tmp_path)
    rows = {r["user_id"]: r for r in csv.DictReader(open(tmp_path / "manager_names.csv"))}
    assert len(rows) >= 12                      # every user_id in history
    assert rows["735974647736213504"]["real_name"] == "Brad"
```
(u2-removal test relies on `tiny`, so the conftest import chain must load — that is intended: conftest fails until LeagueData exists.)

- [ ] **Step 3: Run tests, verify failure** — `pytest tests/test_loading.py -v` → collection error (`No module named leaguestats`).

- [ ] **Step 4: Implement `leaguestats/loading.py`.** Key parts:

```python
from dataclasses import dataclass, field
from pathlib import Path
import csv
import pandas as pd
import yaml

@dataclass
class LeagueData:
    matchups: pd.DataFrame
    drafts: pd.DataFrame
    standings: pd.DataFrame
    player_weeks: pd.DataFrame
    player_points: pd.DataFrame
    transactions: pd.DataFrame
    settings: pd.DataFrame
    managers: pd.DataFrame
    brackets: pd.DataFrame
    names: dict = field(default_factory=dict)
    handles: dict = field(default_factory=dict)
    avatars: dict = field(default_factory=dict)
    lore: dict = field(default_factory=dict)

    def played_seasons(self):
        s = self.settings
        return sorted(s[s.status.isin(["complete", "in_season", "post_season"])]
                      .season.astype(int).tolist())

    def era(self, season: int) -> str:
        row = self.settings[self.settings.season.astype(int) == int(season)]
        n = int(row.iloc[0]["teams"]) if len(row) else 12
        return f"{n}-team"

    def r2u(self, season: int) -> dict:
        g = self.managers[self.managers.season.astype(int) == int(season)]
        return dict(zip(g.roster_id.astype(int), g.user_id))

    def display(self, user_id: str) -> str:
        return self.names.get(user_id) or self.handles.get(user_id, str(user_id))

    def reg_matchups(self) -> pd.DataFrame:
        m = self.matchups.copy()
        for c in ("season", "week", "roster_id", "opponent_roster_id"):
            m[c] = m[c].astype(int)
        for c in ("points", "opponent_points"):
            m[c] = m[c].astype(float)
        if m.is_playoff.dtype == object:
            m["is_playoff"] = m.is_playoff.astype(str).eq("True")
        m = m[~m.is_playoff]
        u = self.managers[["season", "roster_id", "user_id"]].copy()
        u["season"] = u.season.astype(int); u["roster_id"] = u.roster_id.astype(int)
        m = m.merge(u, on=["season", "roster_id"], how="left")
        m = m.merge(u.rename(columns={"roster_id": "opponent_roster_id",
                                      "user_id": "opponent_user_id"}),
                    on=["season", "opponent_roster_id"], how="left")
        return m
```
`load_data(base)` reads every CSV with `pd.read_csv(..., dtype={"user_id": str, "player_id": str})` (both columns overflow/precision-break otherwise — Sleeper ids are 18-digit), assembles `names` from `manager_names.csv` (skip blank real_name), `handles`/`avatars` from the latest season each user appears in `managers.csv` (avatar requires adding an `avatar` column to `pull_managers` — go back and add `"avatar": u.get("avatar") or ""` to the by_user dict and managers.csv fields in the puller, then re-run `./run.sh` to regenerate). `lore` = `yaml.safe_load` or `{}` if the file is missing/empty. `write_name_template(base)` merges existing real names over the full user_id list from `managers.csv` and rewrites the file sorted by handle. Playoff matchup filtering: `matchups_all.csv` stores `is_playoff` as `True`/`False` strings — normalize as shown.

- [ ] **Step 5: Generate the hand-maintained templates.** Add to `load_data`'s module a `__main__` guard: `write_name_template(Path(__file__).resolve().parent.parent)` plus write `league_lore.yml` if absent with:

```yaml
# Hand-maintained league lore. The site renders placeholders until this is filled in.
trophy_name: ""            # what the champion's trophy is called
punishments: {}            # season -> what last place had to do, e.g. 2024: "Ate a ghost pepper"
champion_notes: {}         # season -> one-liner about that title run
```
Run `.venv/bin/python -m leaguestats.loading`. Confirm `manager_names.csv` lists every historical user with blank real_name.

- [ ] **Step 6: Run tests to verify pass** — `pytest tests/test_loading.py tests/test_validation.py -v` → all PASS.

- [ ] **Step 7: Commit** — includes regenerated `data/managers.csv` with avatar column.

---

### Task 4: Career / franchise stats (`leaguestats/career.py`)

**Files:**
- Create: `leaguestats/career.py`, `tests/test_career.py`

**Interfaces:**
- Consumes: `LeagueData` (Task 3): `standings`, `reg_matchups()`, `display()`, `played_seasons()`
- Produces: `compute_career(data: LeagueData) -> dict` with keys:
  - `managers`: list of dicts sorted by `win_pct` desc — `{user_id, name, handle, avatar, seasons, wins, losses, ties, win_pct, pf, pa, avg_finish, titles, playoff_apps, last_places, longest_win_streak, longest_loss_streak, active}` (`active` = appears in the newest season in `managers.csv`)
  - `finish_by_year`: `{user_id: {season: finish}}` (played seasons only; missing season = not in league)
  - `seasons`: list of `{season, era, champion_user, champion_name, last_user, last_name}`

Fixture expectations (see conftest schedule comment): u1 career 2-1, pf 345, titles 1, avg_finish 2, longest_win_streak 1 (W-L-W), u3 streak 3, u4 longest_loss_streak 3 and last_places 1.

- [ ] **Step 1: Write failing tests** — `tests/test_career.py`:

```python
from leaguestats.career import compute_career

def test_career_basics(tiny):
    out = compute_career(tiny)
    by = {m["user_id"]: m for m in out["managers"]}
    assert by["u1"]["wins"] == 2 and by["u1"]["losses"] == 1
    assert by["u1"]["titles"] == 1 and by["u1"]["name"] == "Al"
    assert by["u1"]["pf"] == 345.0 and by["u1"]["avg_finish"] == 2.0
    assert by["u4"]["last_places"] == 1 and by["u4"]["playoff_apps"] == 0

def test_streaks(tiny):
    out = compute_career(tiny)
    by = {m["user_id"]: m for m in out["managers"]}
    assert by["u3"]["longest_win_streak"] == 3   # W W W
    assert by["u1"]["longest_win_streak"] == 1   # W L W
    assert by["u4"]["longest_loss_streak"] == 3

def test_finish_by_year_and_seasons(tiny):
    out = compute_career(tiny)
    assert out["finish_by_year"]["u3"][2024] == 1
    s = out["seasons"][0]
    assert s["champion_user"] == "u1" and s["last_user"] == "u4"
```

- [ ] **Step 2: Run to verify fail** — `pytest tests/test_career.py -v` → `No module named leaguestats.career`.

- [ ] **Step 3: Implement.** Core: filter `standings` to rows with non-empty `finish` (that excludes 2026), aggregate per `user_id` with pandas groupby (`seasons=("season","nunique")`, sums for W/L/T/PF/PA, `avg_finish=("finish","mean")` rounded 2, `titles=("champion","sum")`, `playoff_apps=("made_playoffs","sum")`, `last_places` = count of rows where `finish == max finish that season` — compute per season, not a constant 10/12). Streaks: from `reg_matchups()` sorted by (season, week) per user, count consecutive `result == "W"` / `"L"` runs — write a small pure helper `longest_run(results: list[str], target: str) -> int`. `win_pct = wins / (wins+losses+ties)` rounded 4. Round `pf`/`pa` to 2. `active`: user appears in `managers.csv` rows for `settings.season.max()`.

- [ ] **Step 4: Run to verify pass** — `pytest tests/test_career.py -v` → PASS.
- [ ] **Step 5: Commit.**

---

### Task 5: Head-to-head (`leaguestats/headtohead.py`)

**Files:**
- Create: `leaguestats/headtohead.py`, `tests/test_headtohead.py`

**Interfaces:**
- Consumes: `LeagueData.matchups` (ALL matchups incl. playoffs — H2H is all-time), `managers`, `display()`
- Produces: `compute_h2h(data) -> dict`:
  - `users`: ordered list of `{user_id, name}` (career games desc) — grid axis order
  - `grid`: `{a_user_id: {b_user_id: {w, l, t, avg_margin, streak}}}` (both directions present; `streak` like `"W2"` = a has won last 2 meetings; `avg_margin` from a's perspective, 2dp)
  - `pairs`: `{"a|b" (user ids sorted): [{season, week, is_playoff, a_points, b_points, winner_user}]}` — full meeting log for the click-through view
  - `reg_playoff_split`: `{a|b: {reg: [w,l,t], playoff: [w,l,t]}}` (from a = first id in sorted key)

Fixture: u1 vs u3 met twice — week 2 regular (105-120 L) and week 4 playoff (100-90 W) → overall 1-1, split reg [0,1,0] / playoff [1,0,0], avg_margin (−15+10)/2 = −2.5, streak "W1".

- [ ] **Step 1: Failing tests** — `tests/test_headtohead.py`:

```python
from leaguestats.headtohead import compute_h2h

def test_grid_symmetric_and_correct(tiny):
    out = compute_h2h(tiny)
    a = out["grid"]["u1"]["u3"]
    assert (a["w"], a["l"]) == (1, 1) and a["avg_margin"] == -2.5
    b = out["grid"]["u3"]["u1"]
    assert (b["w"], b["l"]) == (1, 1) and b["avg_margin"] == 2.5
    assert out["grid"]["u1"]["u2"] == {"w": 1, "l": 0, "t": 0,
                                       "avg_margin": 10.0, "streak": "W1"}

def test_pair_log_and_split(tiny):
    out = compute_h2h(tiny)
    key = "u1|u3"
    assert len(out["pairs"][key]) == 2
    assert out["reg_playoff_split"][key] == {"reg": [0, 1, 0], "playoff": [1, 0, 0]}
    assert out["grid"]["u1"]["u3"]["streak"] == "W1"
```

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement.** Merge `user_id`/`opponent_user_id` onto ALL matchups (same merge as `reg_matchups` but without the playoff filter — factor that merge into a loading helper `with_users(matchups_df)` if cleaner). Deduplicate mirrored rows by keeping `roster_id < opponent_roster_id` per (season, week), then emit both perspectives when building the grid. Sort meetings by (season, week) for streak computation (walk from the end while result matches the last result).

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit.**

---

### Task 6: Luck & schedule (`leaguestats/luck.py`)

**Files:**
- Create: `leaguestats/luck.py`, `tests/test_luck.py`

**Interfaces:**
- Consumes: `reg_matchups()`, `display()`
- Produces:
  - Pure: `allplay_week(scores: dict[str, float]) -> dict[str, tuple[int, int, int]]` — key → (w, l, t) vs every other key that week.
  - `compute_luck(data) -> dict`:
    - `seasons`: `{season: [{user_id, name, allplay_w, allplay_l, allplay_t, allplay_pct, exp_wins, actual_wins, luck_delta, close_w, close_l, sos}]}` (`exp_wins` = allplay_pct × games, 2dp; `luck_delta` = actual − expected, 2dp; close = margin < 5; `sos` = mean of that season's opponents' all-play pct, one term per game played, 4dp)
    - `career`: same shape aggregated over all seasons (era-safe because all-play is computed per-week before aggregation)
    - `heists`: top 10 `{season, week, user_id, name, points, opp_points, opp_user_id}` lowest winning scores all-time
    - `robbed`: top 10 highest losing scores, same shape

Fixture: week-by-week all-play totals — u1 8-1, u2 4-5, u3 6-3, u4 0-9. exp_wins u1 = 8/9×3 = 2.67, luck_delta = 2 − 2.67 = −0.67. u3: exp 2.0, delta +1.0. Close games: only w3 r2 100 vs r3 101 → u3 close 1-0, u2 close 0-1. Lowest winning score: u3's 90 (w1). Highest losing score: u1's 105 (w2).

- [ ] **Step 1: Failing tests**:

```python
from leaguestats.luck import allplay_week, compute_luck

def test_allplay_week_pure():
    r = allplay_week({"a": 110.0, "b": 100.0, "c": 90.0, "d": 80.0})
    assert r["a"] == (3, 0, 0) and r["c"] == (1, 2, 0)
    t = allplay_week({"a": 100.0, "b": 100.0, "c": 50.0})
    assert t["a"] == (1, 0, 1) and t["c"] == (0, 2, 0)

def test_season_luck(tiny):
    out = compute_luck(tiny)
    row = {r["user_id"]: r for r in out["seasons"][2024]}
    assert (row["u1"]["allplay_w"], row["u1"]["allplay_l"]) == (8, 1)
    assert row["u1"]["exp_wins"] == 2.67 and row["u1"]["luck_delta"] == -0.67
    assert row["u3"]["luck_delta"] == 1.0
    assert (row["u3"]["close_w"], row["u2"]["close_l"]) == (1, 1)
    # u1 faced u2, u3, u4 whose all-play pcts are 4/9, 6/9, 0/9 -> mean 10/27
    assert row["u1"]["sos"] == 0.3704

def test_heists_and_robbed(tiny):
    out = compute_luck(tiny)
    assert out["heists"][0]["points"] == 90.0 and out["heists"][0]["user_id"] == "u3"
    assert out["robbed"][0]["points"] == 105.0 and out["robbed"][0]["user_id"] == "u1"
```

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement.** Group `reg_matchups()` deduped one-row-per-team (each team-week already has exactly one row per perspective — group by (season, week) and feed `{user_id: points}` to `allplay_week`). Career aggregates the per-week tuples, then computes pct/exp/delta from totals.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit.**

---

### Task 7: Lineup efficiency & benchings (`leaguestats/lineups.py`)

**Files:**
- Create: `leaguestats/lineups.py`, `tests/test_lineups.py`

**Interfaces:**
- Consumes: `player_weeks`, `settings.roster_positions` (per season, `|`-separated), `reg_matchups()` (for results/opponent points), `display()`
- Produces:
  - Pure: `optimal_points(players: list[tuple[str, float]], slots: list[str]) -> float` — players are (position, points); slots is the starting-slot list (BN/IR already stripped).
  - `compute_lineups(data) -> dict`:
    - `seasons`: `{season: [{user_id, name, actual, optimal, efficiency, bench_left}]}` (sums over regular-season weeks; efficiency 4dp)
    - `career`: same aggregated
    - `worst_benchings`: top 15 all-time `{season, week, user_id, name, actual, optimal, delta, result, would_have_won, biggest_miss_player, biggest_miss_points}` sorted by delta desc. `would_have_won` = result == "L" and optimal > opponent points. `biggest_miss_player` = highest-scoring benched player that week.

Slot eligibility (module constant — the league's slot family is laminar, so greedy most-restrictive-first is provably optimal; the brute-force test below guards the claim):
```python
ELIGIBLE = {
    "QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"},
    "K": {"K"}, "DEF": {"DEF"},
    "FLEX": {"RB", "WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
}
```

- [ ] **Step 1: Failing tests**:

```python
import itertools
from leaguestats.lineups import optimal_points, compute_lineups, ELIGIBLE

SLOTS = ["QB", "RB", "FLEX", "SUPER_FLEX"]

def brute_force(players, slots):
    best = 0.0
    for perm in itertools.permutations(range(len(players)), len(slots)):
        total = 0.0
        ok = True
        for slot, pi in zip(slots, perm):
            pos, pts = players[pi]
            if pos not in ELIGIBLE[slot]:
                ok = False
                break
            total += pts
        if ok:
            best = max(best, total)
    return best

def test_optimal_week1_roster1():
    players = [("QB", 30.0), ("QB", 35.0), ("RB", 20.0), ("RB", 28.0),
               ("WR", 25.0), ("WR", 10.0)]
    assert optimal_points(players, SLOTS) == 118.0
    assert optimal_points(players, SLOTS) == brute_force(players, SLOTS)

def test_optimal_matches_brute_force_random():
    import random
    rng = random.Random(7)
    full = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "K", "DEF"]
    poses = ["QB", "RB", "WR", "TE", "K", "DEF"]
    for _ in range(50):
        players = [(rng.choice(poses), round(rng.uniform(0, 30), 2))
                   for _ in range(rng.randint(8, 13))]
        assert abs(optimal_points(players, full) - brute_force(players, full)) < 1e-9

def test_compute_lineups(tiny):
    out = compute_lineups(tiny)
    row = {r["user_id"]: r for r in out["seasons"][2024]}["u1"]
    assert row["actual"] == 110.0 and row["optimal"] == 118.0
    assert row["efficiency"] == 0.9322
    wb = out["worst_benchings"][0]
    assert wb["user_id"] == "u1" and wb["delta"] == 8.0
    assert wb["biggest_miss_player"] == "RB_B" and wb["would_have_won"] is False
```

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement.** `optimal_points`: sort slots by `len(ELIGIBLE[slot])` ascending; for each, take the max-points remaining eligible player (list of players sorted desc once; mark used indexes). Missing/empty positions score 0 (fewer players than slots is legal early in 2021 data). Skip slot names not in `ELIGIBLE` (`BN`, `IR` are stripped by the caller anyway). `compute_lineups`: filter `player_weeks` to `is_playoff == 0`; per (season, week, roster_id) group: actual = started sum, optimal = `optimal_points` over ALL rostered rows that week, slots from that season's `roster_positions` minus BN/IR. Join results/opponent from `reg_matchups()` on (season, week, roster_id). Note the fixture only details roster 1 — the module must not crash on rosters with zero player_weeks rows (2026, idle weeks); those team-weeks are simply absent.

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit.**

---

### Task 8: Draft analysis (`leaguestats/draftstats.py`)

**Files:**
- Create: `leaguestats/draftstats.py`, `tests/test_draftstats.py`

**Interfaces:**
- Consumes: `drafts`, `player_points`, `standings`, `display()`, `era()`
- Produces: `compute_drafts(data) -> dict`:
  - `slot_outcomes`: `[{slot, n, avg_finish, titles, playoff_rate, era_note}]` — joins standings `draft_slot`/`finish`; because 10-team and 12-team eras have different slot counts, every row carries `era_note` and slots > 10 have n < others
  - `steals`: top 15 `{season, manager_user, name, player_name, position, round, overall_pick, points, surplus}` by surplus; `busts`: bottom 15 (rounds 1–8 only — a round-16 zero is not a bust)
  - `by_round`: `[{round, avg_points, hit_rate}]` (hit = points ≥ round avg)
  - `qb_timing`: `[{season, user_id, name, first_qb_round, qbs_in_first_5, finish}]` — the superflex question
  - `tendencies`: `{user_id: {position: pct_of_picks}}` (rounds 1–10, non-keeper picks)
  - `surplus` definition (same as baseline): player `points_regular` that season minus the mean `points_regular` of all players drafted in the same (season, round). Non-keeper picks only for the round mean? NO — baseline includes all picks in the mean; keep that, but exclude keeper picks from `steals` (a keeper at a discounted round is definitionally a steal — they get their own table in Task 9).

Fixture: round averages 157.5 / 90 / 45. P11 surplus = +42.5. P34 (u4, round 3) = 10 − 45 = −35. Keeper P31 (u1) excluded from steals list.

- [ ] **Step 1: Failing tests**:

```python
from leaguestats.draftstats import compute_drafts

def test_surplus_and_steals(tiny):
    out = compute_drafts(tiny)
    top = out["steals"][0]
    assert top["player_name"] == "P11" and top["surplus"] == 42.5
    assert all(s["player_name"] != "P31" for s in out["steals"])  # keeper excluded
    worst = out["busts"][0]
    assert worst["player_name"] == "P24" and worst["surplus"] == -50.0

def test_slot_outcomes_and_qb_timing(tiny):
    out = compute_drafts(tiny)
    slot1 = next(r for r in out["slot_outcomes"] if r["slot"] == 1)
    assert slot1["titles"] == 1 and slot1["avg_finish"] == 2.0
    qt = {r["user_id"]: r for r in out["qb_timing"]}
    assert qt["u1"]["first_qb_round"] == 1 and qt["u1"]["finish"] == 2
    # u1's non-keeper picks: P11 (QB), P21 (RB) — P31 is a keeper and excluded
    assert out["tendencies"]["u1"] == {"QB": 0.5, "RB": 0.5}
```
(Bust check: P24 = 40 − 90 = −50, round 2 ≤ 8. P34 is −35 but P24 is worse.)

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement.** Join `drafts` (played seasons only, non-empty `player_id`) to `player_points` on (season, player_id) with `points_regular` filled 0 where missing (drafted, never rostered). Slot outcomes join `standings` on (season, `slot_owner_roster_id` → roster's slot: use standings' own `draft_slot` column directly — it is already the owned-slot mapping from the puller). `qb_timing`: group non-keeper picks per (season, user), min round where position == "QB".
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit.**

---

### Task 9: Keepers (`leaguestats/keepers.py`)

**Files:**
- Create: `leaguestats/keepers.py`, `tests/test_keepers.py`

**Interfaces:**
- Consumes: `drafts`, `transactions`, `player_points`, `settings` (draft_start_ms), `r2u()`, `display()`
- Produces:
  - `KEEPER_MIN_ROUND = 6`, `MAX_KEEPERS = 2` (module constants)
  - `left_roster(data, season: int, player_id: str, user_id: str) -> bool` — did the player leave that manager's roster during `season`? True if (a) that season's draft shows a different user drafting him, or (b) a completed drop, or any completed trade row, for that player from a roster owned by that user, created at/after that season's `draft_start_ms`.
  - `audit_keepers(data) -> list[dict]` — one row per keeper pick that has a prior-season draft record: `{season, user_id, name, player_id, player_name, prev_round, keep_round, left, need, charged_ok, eligible_round, repeat_keep}` where `need = prev_round - 1 if left else prev_round`, `charged_ok = keep_round == need`, `eligible_round = prev_round >= KEEPER_MIN_ROUND`, `repeat_keep` = player was also a keeper in the prior season's draft.
  - `compute_keepers(data) -> dict`: `{rules: [str, ...] (the four rules verbatim from the spec), audit, summary: {n, charged_ok, rule_flags}, value: [{season, user_id, name, player_name, keep_round, points, surplus}] (surplus vs that season+round draft mean, keepers only), by_manager: [{user_id, name, keeps, avg_surplus, hit_rate}], declared_next: [{user_id, name, player_name, round}] (keeper picks in the newest pre_draft season's draft, [] if none)}`

The conftest fixture is single-season; keeper audit needs two. Build a local two-season fixture in the test file — this also documents the audit contract precisely.

- [ ] **Step 1: Failing tests** — `tests/test_keepers.py`:

```python
import pandas as pd
import pytest
from leaguestats.keepers import left_roster, audit_keepers

def _mini(tiny):
    """Graft a 2023 season onto the tiny fixture to exercise the audit."""
    d23 = pd.DataFrame([
        # u1 drafts KX rd 7 and keeps him honestly at rd 7 in 2024
        dict(season=2023, round=7, overall_pick=25, draft_slot=1,
             slot_owner_roster_id=1, roster_id=1, traded_pick=0, user_id="u1",
             manager="h1", player_id="KX", player_name="KX", position="WR",
             is_keeper=False),
        # u2 drafts KY rd 6, drops him mid-season, keeps him at rd 5 (correct: 6-1)
        dict(season=2023, round=6, overall_pick=22, draft_slot=2,
             slot_owner_roster_id=2, roster_id=2, traded_pick=0, user_id="u2",
             manager="h2", player_id="KY", player_name="KY", position="RB",
             is_keeper=False),
        # u3 drafts KZ rd 3 — round-ineligible to keep
        dict(season=2023, round=3, overall_pick=9, draft_slot=3,
             slot_owner_roster_id=3, roster_id=3, traded_pick=0, user_id="u3",
             manager="h3", player_id="KZ", player_name="KZ", position="WR",
             is_keeper=False),
    ])
    k24 = pd.DataFrame([
        dict(season=2024, round=7, overall_pick=25, draft_slot=1,
             slot_owner_roster_id=1, roster_id=1, traded_pick=0, user_id="u1",
             manager="h1", player_id="KX", player_name="KX", position="WR",
             is_keeper=True),
        dict(season=2024, round=6, overall_pick=21, draft_slot=2,   # WRONG round: need 5
             slot_owner_roster_id=2, roster_id=2, traded_pick=0, user_id="u2",
             manager="h2", player_id="KY", player_name="KY", position="RB",
             is_keeper=True),
        dict(season=2024, round=3, overall_pick=9, draft_slot=3,
             slot_owner_roster_id=3, roster_id=3, traded_pick=0, user_id="u3",
             manager="h3", player_id="KZ", player_name="KZ", position="WR",
             is_keeper=True),
    ])
    tiny.drafts = pd.concat([tiny.drafts, d23, k24], ignore_index=True)
    tiny.transactions = pd.concat([tiny.transactions, pd.DataFrame([
        dict(season=2023, transaction_id="t9", week=6, type="free_agent",
             status="complete", created_ms=5000, created_date="2023-10-15",
             roster_id=2, manager="h2", action="drop", player_id="KY",
             player_name="KY", position="RB", faab_bid=""),
    ])], ignore_index=True)
    m23 = tiny.managers.assign(season=2023)
    tiny.managers = pd.concat([tiny.managers, m23], ignore_index=True)
    s23 = tiny.settings.iloc[[0]].assign(season=2023, draft_start_ms=100)
    tiny.settings = pd.concat([tiny.settings, s23], ignore_index=True)
    return tiny

def test_left_roster(tiny):
    d = _mini(tiny)
    assert left_roster(d, 2023, "KY", "u2") is True    # dropped mid-season
    assert left_roster(d, 2023, "KX", "u1") is False   # stayed all year

def test_audit(tiny):
    d = _mini(tiny)
    rows = {r["player_id"]: r for r in audit_keepers(d)}
    assert rows["KX"]["charged_ok"] and rows["KX"]["need"] == 7
    assert not rows["KY"]["charged_ok"] and rows["KY"]["need"] == 5
    assert not rows["KZ"]["eligible_round"]
    assert not rows["KX"]["repeat_keep"]
```

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement** — port the baseline's `left_roster`/audit logic (see `/Users/bhagstrom/FootballFantasy/ggg-league/analyze_league.py` lines 358–429) onto the `LeagueData` interface. Keeper value/surplus reuses the same round-mean approach as Task 8 (compute inline; the frames differ enough that sharing code isn't worth a util yet). `declared_next`: newest season in `settings` with status `pre_draft` whose draft CSV has keeper rows.
- [ ] **Step 4: Run to verify pass** (all previous tests still green: `pytest -q`).
- [ ] **Step 5: Commit.**

---

### Task 10: Transactions — FAAB & trades (`leaguestats/txstats.py`)

**Files:**
- Create: `leaguestats/txstats.py`, `tests/test_txstats.py`

**Interfaces:**
- Consumes: `transactions`, `player_weeks`, `standings` (waiver_budget_used), `display()`
- Produces: `compute_transactions(data) -> dict`:
  - `faab_seasons`: `{season: [{user_id, name, spent, points_after, ppd}]}` — completed waiver adds with numeric `faab_bid > 0`; `points_after` = started points by that player for that roster in weeks strictly after the transaction week (same season, regular weeks); `ppd` = points_after / bid, 2dp
  - `best_buys` / `worst_buys`: top/bottom 10 individual buys `{season, week, user_id, name, player_name, bid, points_after, ppd}` (worst restricted to bid ≥ 10)
  - `pickups`: top 10 adds by `points_after` including $0/free-agent adds
  - `trades`: `trade_ledger(data) -> list` — one entry per completed trade: `{transaction_id, season, week, date, sides: [{user_id, name, players_gained: [str], points_after: float}], winner_user_id, margin}` (winner = side with larger points_after; margin 2dp; points_after same definition as FAAB)
  - `activity`: `{user_id: {adds, drops, trades}}` (career, completed only)

- [ ] **Step 1: Failing tests** — extend the fixture inline with post-event player_weeks:

```python
import pandas as pd
from leaguestats.txstats import compute_transactions

def _with_post_rows(tiny):
    tiny.player_weeks = pd.concat([tiny.player_weeks, pd.DataFrame([
        # WAIV_1 started by roster 2 after the week-2 pickup
        dict(season=2024, week=3, roster_id=2, user_id="u2", player_id="WAIV_1",
             player_name="WAIV_1", position="RB", points=35.0, started=1, is_playoff=0),
        # traded players' post-trade production (trade was week 2)
        dict(season=2024, week=3, roster_id=3, user_id="u3", player_id="RB_A",
             player_name="RB_A", position="RB", points=12.0, started=1, is_playoff=0),
        dict(season=2024, week=3, roster_id=1, user_id="u1", player_id="WR_C",
             player_name="WR_C", position="WR", points=22.0, started=1, is_playoff=0),
    ])], ignore_index=True)
    return tiny

def test_faab(tiny):
    out = compute_transactions(_with_post_rows(tiny))
    faab = {r["user_id"]: r for r in out["faab_seasons"][2024]}
    assert faab["u2"]["spent"] == 30 and faab["u2"]["points_after"] == 35.0
    assert faab["u2"]["ppd"] == 1.17
    assert "u4" not in faab            # failed claim ignored
    assert out["best_buys"][0]["player_name"] == "WAIV_1"

def test_trade_ledger(tiny):
    out = compute_transactions(_with_post_rows(tiny))
    t = out["trades"][0]
    sides = {s["user_id"]: s for s in t["sides"]}
    assert sides["u1"]["players_gained"] == ["WR_C"]
    assert sides["u1"]["points_after"] == 22.0 and sides["u3"]["points_after"] == 12.0
    assert t["winner_user_id"] == "u1" and t["margin"] == 10.0
```

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement.** Coerce `faab_bid` with `pd.to_numeric(errors="coerce")`. `points_after` helper shared by FAAB and trades: `_points_after(pw, season, roster_id, player_id, after_week) -> float` (started == 1, is_playoff == 0, week > after_week). Trades: filter `type == "trade" and status == "complete"`, group by `transaction_id`; sides = distinct roster_ids; each side's `players_gained` = its `add` rows. Two-plus-team trades work naturally (sides is a list).
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit.**

---

### Task 11: Record book (`leaguestats/recordbook.py`)

**Files:**
- Create: `leaguestats/recordbook.py`, `tests/test_recordbook.py`

**Interfaces:**
- Consumes: `matchups` (all, incl. playoffs), `reg_matchups()`, `player_weeks`, `player_points`, `standings`, `display()`; imports `longest_run` from `career`
- Produces: `compute_records(data) -> dict` — `{records: [{key, label, value, holder, user_id, detail}]}` with at least these keys (each a single record; detail is human copy like `"Week 3 2024 vs Di"`):
  `team_week_high`, `team_week_low`, `blowout` (largest margin), `nailbiter` (smallest nonzero margin), `season_pf_high`, `season_pf_low`, `season_pa_high` (most points against — the punching-bag award), `playoff_week_high`, `win_streak`, `loss_streak`, `player_week_high` (from player_weeks, started only), `player_season_high` (points_regular), `bench_week_high` (best benched score).
  Regular-season records use regular weeks; `playoff_week_high` uses playoff weeks; label says which.

Fixture expectations: team_week_high 130 (Al, w3); team_week_low 70 (Di, w3); blowout margin 60 (Al over Di w3); nailbiter margin 1 (Cy over Bo w3); season_pf_high 345 Al; playoff_week_high 100 Al; player_week_high 35 QB_B (Al); bench_week_high 28 RB_B.

- [ ] **Step 1: Failing tests**:

```python
from leaguestats.recordbook import compute_records

def test_records(tiny):
    out = compute_records(tiny)
    r = {x["key"]: x for x in out["records"]}
    assert r["team_week_high"]["value"] == 130.0 and r["team_week_high"]["holder"] == "Al"
    assert r["blowout"]["value"] == 60.0
    assert r["nailbiter"]["value"] == 1.0 and r["nailbiter"]["holder"] == "Cy"
    assert r["season_pf_high"]["value"] == 345.0
    assert r["season_pa_high"]["value"] == 315.0 and r["season_pa_high"]["holder"] == "Di"
    assert r["playoff_week_high"]["value"] == 100.0
    assert r["player_week_high"]["value"] == 35.0
    assert r["bench_week_high"]["value"] == 28.0 and r["bench_week_high"]["holder"] == "Al"
    assert r["win_streak"]["value"] == 3 and r["win_streak"]["holder"] == "Cy"
```

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement** — straightforward max/min scans with `idxmax`/`idxmin`; margins computed on deduped rows (`roster_id < opponent_roster_id`) then attributed to the winner. Streak records reuse `longest_run` over per-user regular-season result sequences.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit.**

---

### Task 12: JSON emit + build orchestrator (`build_site.py`)

**Files:**
- Create: `build_site.py`, `leaguestats/util.py`, `tests/test_build.py`

**Interfaces:**
- Consumes: every `compute_*` (Tasks 4–11), `load_data`, `write_name_template`
- Produces:
  - `util.to_jsonable(obj)` — recursively converts numpy/pandas scalar types (`int64`, `float64`, `bool_`), dict keys included, so `json.dumps` never chokes.
  - `build_site.py` main: `load_data(ROOT)` → `write_name_template(ROOT)` → run all eight compute functions → write `site/data/{career,h2h,luck,lineups,drafts,keepers,transactions,records}.json` + `site/data/meta.json` (`{league_name, seasons: played list, current_season, generated_utc (from env var BUILD_TIME or empty — no Date.now equivalent needed, the Action passes it), lore, era_boundary: 2025}`).
  - `PAGES: list` placeholder constant the render tasks will fill; for now build ends after JSON.

- [ ] **Step 1: Failing tests** — `tests/test_build.py`:

```python
import json
import numpy as np
from leaguestats.util import to_jsonable

def test_to_jsonable():
    obj = {"a": np.int64(3), "b": [np.float64(1.5)], np.int64(2024): {"c": np.bool_(True)}}
    assert json.dumps(to_jsonable(obj)) == '{"a": 3, "b": [1.5], "2024": {"c": true}}'

def test_full_build_on_real_data(tmp_path, monkeypatch):
    import build_site
    monkeypatch.setattr(build_site, "SITE_DATA", tmp_path)
    build_site.build_json()
    for name in ("career", "h2h", "luck", "lineups", "drafts",
                 "keepers", "transactions", "records", "meta"):
        payload = json.loads((tmp_path / f"{name}.json").read_text())
        assert payload, name
```

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement.** `build_site.py` structure: module constants `ROOT = Path(__file__).parent`, `SITE_DATA = ROOT / "site" / "data"`; `build_json()` does the load/compute/write loop and returns the dict-of-dicts (render tasks reuse it); `__main__` calls `build_json()`. The real-data test doubles as an integration test of every module against all five seasons — expect it to surface real-data edge cases (missing positions on old players, empty FAAB seasons); fix them in the module where they arise, not with try/except in the builder.
- [ ] **Step 4: Run to verify pass** — `pytest -q` fully green; run `.venv/bin/python build_site.py` and spot-check `site/data/career.json` numbers against the friend-report style sanity: five seasons, champions match `standings` champion rows.
- [ ] **Step 5: Commit** (including generated `site/data/*.json`).

---

### Task 13: Site shell — design system, charts, renderer

**Files:**
- Create: `leaguestats/charts.py`, `leaguestats/render.py`, `templates/base.html.j2`, `site/assets/css/style.css`, `site/assets/js/tables.js`, `tests/test_charts.py`, `tests/test_render.py`

**Interfaces:**
- Consumes: nothing from stats modules (pure presentation layer)
- Produces (used by Tasks 14–16):
  - `charts.svg_line(series: list[tuple[str, list]], x_labels: list[str], *, w=640, h=280, y_invert=False) -> str` — multi-series line chart; `None` gaps allowed; `y_invert=True` for finish trajectories (1 at top)
  - `charts.svg_bar(items: list[tuple[str, float]], *, w=640, h=280, highlight: str | None = None) -> str`
  - `charts.svg_heatmap(row_labels: list[str], col_labels: list[str], values: dict[tuple[str, str], float | None], *, cell=40, fmt="{:.0f}") -> str` — for the H2H win-pct grid
  - `render.env() -> jinja2.Environment` (loads `templates/`, autoescape on, filters: `fmt2` → `f"{x:,.2f}"`, `fmt0` → `f"{x:,.0f}"`, `pct` → `f"{x*100:.1f}%"`)
  - `render.render_page(template: str, ctx: dict, out_path: Path) -> None`
  - `render.slug(s: str) -> str` — lowercase, non-alphanumeric → `-`, used for manager page filenames
  - `templates/base.html.j2` blocks: `title`, `content`; top nav links: `index.html`, `seasons.html`, `managers.html`, `h2h.html`, `records.html`, `draft.html`, `trades.html`, `champions.html` (all site-root-relative via a `root` ctx var, e.g. `{{ root }}records.html`, so nested pages link correctly)

**Design directive (governs this task and Tasks 14–16):** the repo root has `PRODUCT.md` — the impeccable skill's product record, written with the user before execution. Read it first. Then, before any CSS or markup: invoke the `impeccable` skill, run its setup script (`context.mjs`), and follow its **new-work** flow to choose and commit the site's visual world (`DESIGN.md` + surface briefs) — expect mostly Operate/Read modes for stats surfaces, but let new-work decide per surface, honoring whatever brand commitments PRODUCT.md pins. Load the skill's `craft-floor.md` immediately before editing UI files. Invoke the `dataviz` skill before writing `charts.py`. Iterate on visuals in a real browser: `python3 -m http.server 8100 --directory site` + the browser MCP tools. Dark-mode-first with a `prefers-color-scheme: light` variant; system font stack; Sleeper avatars via `https://sleepercdn.com/avatars/thumbs/{avatar_id}` with a CSS-initial fallback when blank. These are constraints for new-work, not a substitute for it.

- [ ] **Step 1: Failing chart/render tests**:

```python
from pathlib import Path
from leaguestats.charts import svg_line, svg_bar, svg_heatmap
from leaguestats.render import render_page, slug

def test_svg_line_basic():
    svg = svg_line([("Al", [1, 3, None, 2])], ["21", "22", "23", "24"], y_invert=True)
    assert svg.startswith("<svg") and 'class="series"' in svg
    assert svg.count("<circle") == 3          # None week draws no point

def test_svg_heatmap_skips_none():
    svg = svg_heatmap(["a"], ["b"], {("a", "b"): None})
    assert "<svg" in svg and "rect" in svg

def test_slug():
    assert slug("KingTowsk") == "kingtowsk"
    assert slug("Jack Taco 98!") == "jack-taco-98"

def test_render_page(tmp_path):
    out = tmp_path / "x.html"
    render_page("base.html.j2", {"root": ""}, out)
    html = out.read_text()
    assert "<nav" in html and "records.html" in html
```

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement charts + renderer + base template + CSS + JS.** `tables.js` (complete, ship as written):

```javascript
// Click a <th> of any table.sortable to sort by that column. Numeric-aware.
document.querySelectorAll("table.sortable th").forEach((th, i) => {
  th.addEventListener("click", () => {
    const tbody = th.closest("table").querySelector("tbody");
    const dir = th.dataset.dir === "asc" ? -1 : 1;
    th.closest("tr").querySelectorAll("th").forEach(h => delete h.dataset.dir);
    th.dataset.dir = dir === 1 ? "asc" : "desc";
    const val = tr => tr.children[i].dataset.sort ?? tr.children[i].textContent.trim();
    const num = s => s !== "" && !isNaN(s.replace(/,/g, ""));
    [...tbody.rows]
      .sort((a, b) => {
        const [x, y] = [val(a), val(b)];
        return (num(x) && num(y)
          ? parseFloat(x.replace(/,/g, "")) - parseFloat(y.replace(/,/g, ""))
          : x.localeCompare(y)) * dir;
      })
      .forEach(tr => tbody.appendChild(tr));
  });
});
```
CSS: design tokens (`--bg`, `--surface`, `--text`, `--muted`, `--accent`, `--win`, `--loss`), max-width 72rem shell, sticky nav, card grid, table styles with right-aligned numerics, `overflow-x:auto` wrappers, avatar chips. Charts: compute scales in Python; emit `<svg viewBox>` with polylines, circles with `<title>` tooltips, axis text at 12px; heatmap cells colored by a two-hue diverging ramp around .500 (win pct) with readable text.
- [ ] **Step 4: Run to verify pass** — `pytest tests/test_charts.py tests/test_render.py -v`.
- [ ] **Step 5: Commit.**

---

### Task 14: Pages — Home, Seasons, Records

**Files:**
- Create: `templates/index.html.j2`, `templates/seasons.html.j2`, `templates/season.html.j2`, `templates/records.html.j2`
- Modify: `build_site.py` (add `build_pages(payload)` and call from `__main__`)
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: `build_json()` return dict (`payload`), `render.render_page`, `charts.*`
- Produces: `site/index.html`, `site/seasons.html` (index of years), `site/seasons/{year}.html` per played season, `site/records.html`. `build_pages(payload: dict) -> list[Path]` returns written paths (Tasks 15–16 extend it).

Page content contracts:
- **index**: hero with league name + season count; reigning champion card (name, avatar, trophy name from lore or placeholder); current punishment holder card (lore); all-time table (career.managers: name, W-L, win%, PF, titles, playoff apps) sortable; 4 marquee records pulled from `records` by key (`team_week_high`, `blowout`, `win_streak`, `season_pf_high`); finish-trajectory `svg_line` of all managers (y_invert).
- **season page**: final standings table (finish, name, W-L, PF, PA, luck_delta from `luck.seasons[year]`); weekly results grid (weeks × managers, W/L colored, score in cell, `data-sort` on points); playoff bracket rendered as rounds of matchup cards from `brackets` rows (winners bracket; roster ids → names via that season's crosswalk — pass a per-season `rid_names` dict in ctx); season superlatives (highest week, biggest blowout, luckiest/unluckiest from that season's luck rows).
- **records**: every entry in `records.records` as a card: label, value, holder with avatar, detail line. Group regular/playoff/player/bench by key prefix order given in Task 11.

- [ ] **Step 1: Failing tests** (rendered-output smoke against real data):

```python
from pathlib import Path
import build_site

def test_pages_render(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "SITE", tmp_path)
    monkeypatch.setattr(build_site, "SITE_DATA", tmp_path / "data")
    payload = build_site.build_json()
    written = build_site.build_pages(payload)
    idx = (tmp_path / "index.html").read_text()
    assert "The league" in idx
    champs = [s["champion_name"] for s in payload["career"]["seasons"]]
    assert champs[-1] in idx                      # reigning champion on home page
    s25 = (tmp_path / "seasons" / "2025.html").read_text()
    assert "Weekly results" in s25 and "Bracket" in s25
    assert (tmp_path / "records.html").exists()
    assert all(p.exists() for p in written)
```
(This requires `build_site.SITE = ROOT / "site"` to exist as a constant — add it while implementing.)

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement templates + `build_pages`.** Bracket note: `roster_id_1/2` may be blank (placeholder games); render only rows with both rosters known, ordered by round; label `position == 1` as the Championship. Seasons index = card per year with champion + one-line lore note (`champion_notes`).
- [ ] **Step 4: Run to verify pass; visual check.** Serve `site/` and review every page in the browser at mobile (390px) and desktop widths; fix layout issues before committing.
- [ ] **Step 5: Commit** (generated HTML included).

---

### Task 15: Pages — Managers, Head-to-Head

**Files:**
- Create: `templates/managers.html.j2`, `templates/manager.html.j2`, `templates/h2h.html.j2`
- Modify: `build_site.py` `build_pages()`
- Test: extend `tests/test_pages.py`

**Interfaces:**
- Consumes: payload dicts `career`, `h2h`, `luck`, `lineups`, `drafts`, `keepers`, `transactions`
- Produces: `site/managers.html` (roster of manager cards), `site/managers/{slug}.html` per user ever in the league (slug from display name via `render.slug`, collision → append user_id suffix), `site/h2h.html`

Page content contracts:
- **manager page**: header (avatar, name, handle, active/former badge); career stat strip (W-L, win%, titles, avg finish, luck delta career, lineup efficiency career); finish-by-year `svg_line`; H2H table vs every opponent (from `h2h.grid[user]`, sortable, streak column, link to h2h.html); "Best & worst" cards: top-3 steals and busts by this manager (filter `drafts.steals/busts` full lists — pass unfiltered per-manager variants in the payload: while implementing add `by_manager` breakdowns to `compute_drafts` output (`steals_by_manager: {user_id: [...top5]}`, same for busts) — update Task 8's module and its tests accordingly); keeper history rows (`keepers.value` filtered to user); worst benching moments (filter `lineups.worst_benchings`); FAAB career line (`transactions.faab_seasons` summed).
- **h2h.html**: the full grid as `svg_heatmap` of win pct PLUS an HTML matrix table where each cell links to an anchor section `#u{a}-vs-u{b}` listing the pair's meeting log (from `h2h.pairs`) — pre-render all pair sections server-side; they are small.

- [ ] **Step 1: Failing tests** (append to `tests/test_pages.py`):

```python
def test_manager_and_h2h_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "SITE", tmp_path)
    monkeypatch.setattr(build_site, "SITE_DATA", tmp_path / "data")
    payload = build_site.build_json()
    build_site.build_pages(payload)
    mgr_dir = tmp_path / "managers"
    pages = list(mgr_dir.glob("*.html"))
    assert len(pages) >= 12                        # every manager in history
    one = pages[0].read_text()
    assert "Career" in one and "Head-to-head" in one
    h2h = (tmp_path / "h2h.html").read_text()
    assert "-vs-" in h2h and "<svg" in h2h
```

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement** (including the Task-8 `steals_by_manager`/`busts_by_manager` addition + its test: assert `out["steals_by_manager"]["u1"][0]["player_name"] == "P11"`).
- [ ] **Step 4: Run to verify pass; visual check in browser both widths.**
- [ ] **Step 5: Commit.**

---

### Task 16: Pages — Draft & Keepers, Trades & Waivers, Champions & Shame

**Files:**
- Create: `templates/draft.html.j2`, `templates/trades.html.j2`, `templates/champions.html.j2`
- Modify: `build_site.py` `build_pages()`
- Test: extend `tests/test_pages.py`

Page content contracts:
- **draft.html**: keeper rules card (the four rules, verbatim from spec); audit summary ("N of M keepers charged the correct round") + flagged-rows table; 2026 declared keepers (or "draft not created yet" note); steals/busts tables; `by_round` bar chart (`svg_bar` of avg points); slot-outcomes table with era notes; QB-timing scatter-ish table (first_qb_round vs finish, sortable).
- **trades.html**: FAAB leaderboard per season (tabs = plain anchor sections per year); best/worst buys tables; trade ledger as cards — each side's gains with post-trade points and a winner badge; career activity table.
- **champions.html**: two-column (stacks on mobile): Hall of Champions timeline (year, name+avatar, trophy name, champion_note) opposite Wall of Shame (year, last place, punishment from lore; placeholder copy if lore empty: "History unrecorded — commissioner, fill in league_lore.yml").

- [ ] **Step 1: Failing tests** (append):

```python
def test_remaining_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "SITE", tmp_path)
    monkeypatch.setattr(build_site, "SITE_DATA", tmp_path / "data")
    payload = build_site.build_json()
    build_site.build_pages(payload)
    draft = (tmp_path / "draft.html").read_text()
    assert "Keeper rules" in draft and "keepers charged" in draft
    trades = (tmp_path / "trades.html").read_text()
    assert "FAAB" in trades
    champs = (tmp_path / "champions.html").read_text()
    assert "Wall of Shame" in champs
```

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Full check + impeccable finish pass.** `pytest -q` all green; `.venv/bin/python build_site.py`; run `validate_data.py`. Then run the impeccable **polish** pass over the whole built site and its **audit** (a11y/responsive/perf) — bounded per the skill's verification rules: one batched inspection round (desktop 1280px + mobile 390px, every page), fix everything found in one batch, confirm with at most one more round, stop. Fix anything off before commit.
- [ ] **Step 5: Commit.**

---

### Task 17: README, GitHub Action, repo publish, Pages

**Files:**
- Create: `README.md`, `.github/workflows/update.yml`

**Interfaces:**
- Consumes: everything; `run.sh --build` and full `run.sh` as the two entry points
- Produces: live site at `https://<owner>.github.io/the-league/`

- [ ] **Step 1: Write `.github/workflows/update.yml`** (complete, ship as written):

```yaml
name: Update data and deploy site
on:
  workflow_dispatch:
  push:
    branches: [main]
  schedule:
    # Tuesdays 14:00 UTC (~9am ET), September–January: after MNF stats settle.
    - cron: "0 14 * 9-12,1 2"
permissions:
  contents: write
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: false
jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - name: Pull fresh data (scheduled/manual runs only)
        if: github.event_name != 'push'
        run: python pull_league_data.py
      - run: python validate_data.py
      - run: python build_site.py
        env:
          BUILD_TIME: ${{ github.run_started_at }}
      - name: Commit refreshed data
        if: github.event_name != 'push'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add -A
          git diff --cached --quiet || git commit -m "data: scheduled refresh"
          git push
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site
      - uses: actions/deploy-pages@v4
```
(Push-triggered runs skip the pull and the data commit, so the scheduled run's push does not loop: it triggers a push run that rebuilds identical output and deploys, committing nothing.)

- [ ] **Step 2: Write `README.md`.** Follow the baseline README's structure (it is good): what this is + site link, quick start (`./run.sh`), rolling the league forward (one constant), the keeper rules, repo layout, the data gotchas section (adapted, including the new `player_weeks`/`brackets` outputs), the two hand-maintained files (`manager_names.csv`, `league_lore.yml`) with fill-in instructions, and a note that `site/` + `REPORT`-equivalent JSON are generated — never hand-edit.

- [ ] **Step 3: Publish.** Check `gh auth status`. Then:
```bash
OWNER=$(gh api user -q .login)
gh repo create "$OWNER/the-league" --public --source . --push
gh api -X POST "repos/$OWNER/the-league/pages" -f build_type=workflow || true  # enable Pages (Actions source); ok if exists
```
If `gh` is not authenticated, STOP and ask the user to run `! gh auth login` rather than improvising credentials.

- [ ] **Step 4: Verify end-to-end.** `gh workflow run update.yml && gh run watch` → green. `curl -sI "https://$OWNER.github.io/the-league/" | head -1` → HTTP 200 (Pages can take a minute on first deploy; retry briefly). Open the live URL in the browser and click through the nav.

- [ ] **Step 5: Commit any README tweaks and push.** Report the live URL, and remind the user to fill in `manager_names.csv` and `league_lore.yml` and push (or just edit on GitHub — the push-triggered Action rebuilds the site with real names automatically).

---

## Post-plan notes for the executor

- Task order is strict for 1–3 and 12–17; Tasks 4–11 are independent of each other (all depend only on Task 3) and may be parallelized by dispatching subagents if using subagent-driven development — except Task 8, whose output contract is extended during Task 15.
- The real-data smoke tests (Tasks 2, 3, 12, 14–16) run against committed `data/` — they need no network. Only `pull_league_data.py` touches the API.
- If the 2026 draft gains keeper picks mid-project, nothing breaks: 2026 stays out of every played-season computation and `declared_next` starts reporting them.



