# The League — the board

Every draft pick, keeper, matchup, trade, and FAAB dollar the league has on
record since 2021, pulled from the Sleeper API and posted as a website.

**The site:** https://bradhagstrom16.github.io/the-league/ *(live after first deploy)*

| | |
|---|---|
| League | The League (`1315570882550202368`) |
| Seasons | 2021–2026 (10 teams through 2024, 12 since 2025) |
| Format | Superflex keeper, 2 keepers max, $125 FAAB, 6 playoff teams |
| School | Downers Grove North — go Trojans |

Adapted from the excellent [ggg-league](https://github.com/atmoore/ggg-league)
pipeline; same philosophy (committed CSVs, every number recomputed from data),
different output (a full website instead of a markdown report).

---

## Quick start

Sleeper's read API is public. No login, no API key. You need Python 3.9+.

```bash
git clone <this repo>
cd the-league
./run.sh              # pull fresh data, validate, rebuild the site
./run.sh --build      # validate + rebuild only, no network
python3 -m http.server 8123 --directory site   # view it locally
```

The GitHub Action does the same thing every Tuesday morning during the season
(and on every push to main), then deploys `site/` to GitHub Pages. There is
nothing to maintain in season.

## Rolling the league forward each season

Each season's league object carries a `previous_league_id`, so history is a
linked list. When the 2027 league exists, change one constant at the top of
`pull_league_data.py`:

```python
ROOT_LEAGUE_ID = "<the new season's league id>"
```

Everything earlier is rediscovered automatically.

## The two hand-maintained files

Everything else regenerates from the API. These two do not:

- **`manager_names.csv`** maps Sleeper handles to real first names. Blank
  names fall back to handles (that's what the site shows today). Fill in the
  `real_name` column and push — the Action rebuilds with real names.
- **`league_lore.yml`** holds what Sleeper can't know: the trophy's name,
  the punishment each last-place finisher served, one-liners about title
  runs. The Champions & Shame page renders honest placeholders until this
  is filled in.

## Keeper rules on the board

1. A manager may keep 2 players maximum.
2. The player must have been drafted in the previous year's draft in round 6
   or later. A player may not be kept two years in a row.
3. You keep a player at the round you drafted him — one round earlier if he
   ever left your roster.
4. Draft pick trading is allowed before and during the draft, including
   keepers. Future years' picks cannot be traded.

Sleeper enforces none of this. The draft page audits every historical keeper
against these rules; 19 of 69 keeps were charged their original round where
rule 3 reads one-round-earlier. Either the penalty isn't really league law or
history has some explaining to do — the board just posts the lines.

## What's in here

```
pull_league_data.py        Sleeper API → data/*.csv (stdlib only)
validate_data.py           pipeline invariants; the Action fails loudly if data is wrong
build_site.py              CSVs → stats → site/data/*.json + rendered HTML
leaguestats/               the stats modules (career, h2h, luck, lineups,
                           drafts, keepers, transactions, records) + charts/render
templates/                 Jinja2 page templates
site/                      the generated site (GitHub Pages serves this) — never hand-edit
data/                      per-season CSVs + *_all.csv — committed so the repo
                           is useful without running anything
tests/                     pytest suite (46 tests, incl. hand-computed fixtures
                           and a brute-force-verified lineup optimizer)
PRODUCT.md, DESIGN.md      product record and design system (impeccable)
```

## Gotchas worth knowing before you trust a number

Inherited from the baseline repo, verified here, plus two new ones:

- **Draft slot is not the roster that made the pick.** Picks get traded; use
  `slot_owner_roster_id`.
- **~30% of transaction rows are failed waiver claims.** Filter
  `status == "complete"`.
- **`week` is not a date.** Offseason moves report as leg 1; compare
  `created_ms` against draft date.
- **Regular-season points only.** Sleeper reports player points for all 18
  weeks including playoff weeks for eliminated teams.
- **Join on `user_id`, never display name.** `roster_id` is only stable
  within a season.
- **Sleeper's frozen season totals drift from its own weekly data** by up to
  ~6 points for 2021–2024 (stat corrections never backfilled). This repo's
  standings recompute PF/PA from weekly matchup rows so everything
  reconciles; finish order is identical under both sources (verified).
- **An unfilled lineup slot scores zero**, so "optimal lineup" never starts a
  negative-scoring player. The optimizer is verified against exhaustive
  search, including negative weeks.
