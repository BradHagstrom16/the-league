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


if __name__ == "__main__":
    out = build_json()
    n = sum(1 for k in out if k != "_data")
    print(f"site/data: {n} JSON payloads written")
