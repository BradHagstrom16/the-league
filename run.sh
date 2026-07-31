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
