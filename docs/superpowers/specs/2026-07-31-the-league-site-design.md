# "The League" Stats Site — Design

**Date:** 2026-07-31
**League:** "The league", Sleeper league ID `1315570882550202368` (2026 season)
**Baseline:** https://github.com/atmoore/ggg-league (Python → CSV → REPORT.md), which this project intends to match in rigor and exceed in presentation and depth.

## Goal

A public, shareable, auto-updating stats website for the league: full history, deep analysis, and a polished visual experience the whole league can browse on their phones. Hosted free on GitHub Pages, refreshed automatically from the Sleeper API during the season.

## The league (facts pulled from the API)

- Six seasons linked via `previous_league_id`: 2021–2024 (10 teams), 2025–2026 (12 teams).
- Superflex roster: QB, 2×RB, 2×WR, TE, FLEX, SUPER_FLEX, K, DEF, 6×BN, 1 IR.
- Keeper league: `max_keepers: 2`. FAAB waivers, $125 budget. 6 playoff teams, playoffs start week 15. Trade deadline week 13.
- 2026 status: `pre_draft`; a 2026 draft object exists (`draft_id 1315570882558574592`).

## Architecture

Python pipeline → committed CSVs → computed JSON → zero-build static site. One language for all logic; the frontend is plain HTML/CSS/JS with no framework and no Node toolchain.

```
pull_league_data.py     Sleeper API → CSVs (stdlib only; walks the previous_league_id chain)
build_site.py           CSVs → stats → site/data/*.json + rendered HTML pages
run.sh                  one command: pull, then build (venv bootstrap like the baseline)
site/                   static site served by GitHub Pages
data/
  drafts/ matchups/ rosters/ transactions/ player_points/ standings/   per-season CSVs
  *_all.csv             combined across seasons
  league_history.csv    per-season standings summary
  managers.csv          roster_id ↔ user_id ↔ display name crosswalk (generated)
  league_settings.csv   per-season settings snapshot (generated)
manager_names.csv       HAND-MAINTAINED: Sleeper handle → real first name
league_lore.yml         HAND-MAINTAINED: trophy name/history, punishment per season, notes
.github/workflows/update.yml   cron (Tue mornings in season) + manual dispatch
docs/superpowers/specs/ this document
tests/                  pytest for the tricky stat computations
```

Rolling forward to 2027: change one `ROOT_LEAGUE_ID` constant; everything earlier is rediscovered via the chain.

## Data pipeline

**Sleeper endpoints** (public, no auth): league, users, rosters, matchups per week, winners/losers bracket, transactions per week, traded picks, drafts + picks, `players/nfl` dump (cached locally; refreshed at most weekly), `state/nfl` for current week.

**Carried-over gotchas from the baseline (pipeline rules):**

- Draft slot ≠ the roster that made the pick; use the draft's `slot_to_roster_id` map (picks get traded).
- ~30% of transaction rows are failed waiver claims — filter `status == "complete"`.
- `week` is not a date; offseason moves report as leg 1. Use `created` timestamps compared against draft date.
- Compute and use `points_regular` (regular-season weeks only), never Sleeper's all-18-week totals.
- Regular-season `finish` is derived (wins, then points for) — Sleeper has no such field. Validate against bracket outcomes.
- Join on `user_id`, never display name; `roster_id` is only stable within a season.

**New for this league:** 10-team (2021–24) vs 12-team (2025–26) eras — league-wide averages and records are annotated with era where team count changes the meaning (e.g., all-play percentages, schedule strength).

## Stats catalog

**Franchise & career:** all-time W-L, PF/PA, average finish, titles, playoff appearances, last places; longest win/loss streaks; hot/cold eras per manager.

**Head-to-head:** full 12×12 all-time grid — record, average margin, current streak; per-pair full matchup history.

**Luck & schedule:** all-play record per week/season/career; expected wins (all-play based) vs actual wins ("luck delta"); close-game (<5 pt) record; unluckiest losses (highest losing scores) and biggest heists (lowest winning scores); strength of schedule.

**Lineup management:** optimal lineup per team-week from per-player scores (respecting slot eligibility incl. superflex); lineup efficiency (actual ÷ optimal); points left on bench; worst benchings ever (incl. "would have won" flags).

**Draft:** slot-vs-finish analysis with the era caveat; steals and busts by round (season points vs draft position); superflex strategy: QB draft timing vs outcomes; per-manager positional tendencies and hit rates by round.

**Keepers:** rule audit for every keeper in history; keeper value rankings (production vs round cost); per-player and per-manager keeper history; 2026 declarations.

Keeper rules (per user: nearly identical to baseline league; wording to confirm):
1. Max 2 keepers.
2. Player must have been drafted round 6 or later the previous year; a player may not be kept two years in a row.
3. Kept at the round drafted; one round earlier if the player ever left the drafting roster (trade, drop/re-add).
4. Pick trading allowed before/during the draft; no future-year picks.

**Transactions:** FAAB efficiency — points per dollar, best/worst buys; waiver pickups of the year (points after acquisition); full trade ledger with retrospective "points gained/lost since trade" per side.

**Records book:** single-week high/low, biggest blowout, closest game, season PF/PA records, streaks, playoff records — each with week, season, and opponent context.

**Lore (hand-maintained):** Hall of Champions with trophy history; Wall of Shame with punishment history per last-place finisher.

## Site

**Pages:** Home (league at a glance: champion, punishment holder, all-time strip, marquee records, latest week in season) · Seasons (per year: standings, weekly results grid, bracket, superlatives) · Managers (per manager: career line, finish trajectory chart, H2H vs everyone, draft/keeper history, best/worst moments, efficiency) · Head-to-Head (interactive grid, click-through to pair history) · Records · Draft & Keepers (explorer, steals/busts, rules + audit, 2026 declarations) · Trades & Waivers · Champions & Shame.

**Visual direction:** dark-mode-first, league branding from Sleeper (name, avatars via Sleeper CDN), hand-built SVG charts (trajectories, distributions, H2H heatmap), sortable tables, mobile-first layouts. No external JS dependencies; site loads instantly. Design/dataviz quality via the impeccable + dataviz skills at implementation time.

**Navigation:** static top nav; every page is a real HTML file (deep-linkable, no client-side routing).

## Automation

GitHub Action `update.yml`:
- Cron: Tuesday ~09:00 UTC during NFL season (Sept–Jan) + `workflow_dispatch` manual button.
- Steps: pull → validate → build → commit CSV/JSON/HTML diff → Pages deploy.
- On any API error or validation failure: fail the run, commit nothing; the previous site stays live.

## Error handling & validation

Pipeline invariants, checked before any write is committed:
- Standings reproduce win/loss/points from raw matchup rows exactly.
- Every matchup has exactly two sides; weekly team points equal the sum of starter player points (within rounding).
- Champion derived from the winners bracket exists and matches a roster in that season.
- Keeper audit: every declared keeper resolves to a previous-season draft pick or an explicit rule exception, which is flagged, never silently dropped.
- Manager crosswalk: every roster in every season maps to a `user_id` and a display name; unmapped handles fall back to Sleeper handles (site still builds if `manager_names.csv` is incomplete).

## Testing

Pytest for computations with real trap potential: all-play records, optimal lineup (slot eligibility incl. superflex/flex assignment), FAAB and trade ledgers, keeper round-cost rule (traded/dropped penalty), era-split aggregation. Fixtures use small hand-checked synthetic seasons. Everything else is covered by the pipeline invariants above.

## Hand-maintained inputs (user to provide)

1. `manager_names.csv` — 12 Sleeper handles → first names (template generated by the puller).
2. `league_lore.yml` — trophy name/history, punishment description + per-season victims/punishments.
3. Confirmation of exact keeper rule wording if it differs from the baseline league's.

## Out of scope (YAGNI)

- Live in-game scoreboards or push notifications.
- Auth, comments, or any server-side component.
- Projections/predictions; the site is a record, not an oracle.
- Non-Sleeper history (any pre-2021 seasons on other platforms) unless the user later supplies data.

## Open questions

- 2021 data completeness: verify matchup/draft data exists for the earliest season during implementation; degrade gracefully (annotate, don't crash) if partial.
- The 2026 draft object exists but is `pre_draft` with `draft_rounds: 3` currently configured — treat 2026 draft data as absent until it completes; keeper declarations may need a hand file like the baseline if declared before Sleeper has them.
- GitHub repo name assumed `the-league` under the user's account; confirm before first push.
