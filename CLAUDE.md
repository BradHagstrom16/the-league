# The League

Stats site for a 12-team Sleeper superflex keeper league (2021 on). Pipeline: Sleeper API → `data/` CSVs → `leaguestats/` (stats) → Jinja2 `templates/` → static `site/` on GitHub Pages. README.md covers setup, rolling the league forward, the hand-maintained files and the full keeper rules; don't repeat it here. League law below keeps only the rulings the code implements.

## Commands

```bash
./run.sh --build                                  # validate + rebuild site/, no network
./run.sh                                          # pull fresh Sleeper data first
.venv/bin/python -m pytest -q                     # tests (pytest.ini sets testpaths and pythonpath)
python3 -m http.server 8123 --directory site      # view locally
```

`run.sh` creates `.venv` on first run. CI uses Python 3.12.

## Workflow

- This repo is PUBLIC. Nothing private (other leagues' data, Subvertadown content, keys) goes here.
- Branch, PR (CodeRabbit and GitGuardian run on it), squash-merge. A PR never exercises the deploy.
- `main` can move without you: the Action runs every Tuesday from August through January (and on the 1st of each month) and commits `data: scheduled refresh` only when the pulled data changed. `git pull` before branching.
- Push to `main` builds and deploys from the committed data without pulling. Scheduled and manual runs pull from Sleeper, commit any data changes, then deploy.
- A blank `finish` means "season not concluded". `pull_league_data.rank_standings` only ranks once Sleeper's status is `complete`, and `career._played_standings` and `validate_data.check_champion` rely on that. A season in progress (2026 from week 1) has matchups but no finish; anything new that lists concluded seasons must key on `finish` the same way.
- Before trusting a fix that touches the pull, simulate the scheduled run in a scratch clone: pytest, `pull_league_data.py`, `validate_data.py`, `build_site.py`, pytest again. A push never runs the pull.
- A shared research repo vendors this one (minus `site/`, `templates/`, `images/`, `build_site.py`) through git subtree, so `leaguestats/` has a second consumer.

## League law (Brad's word is final; don't re-derive from the GGG league, which differs)

- No one-round-earlier penalty for keepers who left a roster.
- Same-round collision: one keeper moves up a round. `keepers._resolve_collisions` grades the two rounds as a set, since the rule doesn't say which one moves.
- The punished loser is the winner of the losers-bracket p=1 game, the "toilet bowl" (`career.toilet_bowl_loser`).

## Design and copy

- DESIGN.md (tokens, "tote board" system) and PRODUCT.md (voice) govern every UI and copy change. Read them first.
- No em dashes in site copy. Use a period, colon, or `·`. Page titles are `X · The League`.
