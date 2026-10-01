# The League

Stats site for a 12-team Sleeper superflex keeper league (2021 on). Pipeline: Sleeper API → `data/` CSVs → `leaguestats/` (stats) → Jinja2 `templates/` → static `site/` on GitHub Pages. README.md covers setup, rolling the league forward, the hand-maintained files and the keeper rules; don't repeat it here.

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
- `main` moves without you: the Action commits `data: scheduled refresh` every Tuesday in season (and on the 1st of each month). `git pull` before branching.
- Push to `main` builds and deploys from the committed data without pulling. Scheduled and manual runs pull from Sleeper, commit the data, then deploy.
- A shared research repo vendors this one (minus `site/`, `templates/`, `images/`, `build_site.py`) through git subtree, so `leaguestats/` has a second consumer.

## League law (Brad's word is final; don't re-derive from the GGG league, which differs)

- No one-round-earlier penalty for keepers who left a roster.
- Same-round collision: one keeper moves up a round. `keepers._resolve_collisions` grades the two rounds as a set, since the rule doesn't say which one moves.
- The punished loser is the winner of the losers-bracket p=1 game, the "toilet bowl" (`career.toilet_bowl_loser`).

## Design and copy

- DESIGN.md (tokens, "tote board" system) and PRODUCT.md (voice) govern every UI and copy change. Read them first.
- No em dashes in site copy. Use a period, colon, or `·`. Page titles are `X · The League`.
