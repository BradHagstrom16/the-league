import os
import time

from pull_league_data import league_date

# The 2025 draft started 2025-09-01 00:49 UTC, which is 2025-08-31 7:49pm
# Central. Every draft in league history ran in the evening, so every one of
# them crosses midnight UTC. Rendering on the runner's clock put Actions a day
# ahead of a Central laptop and flipped the site's dates on alternating runs.
DRAFT_2025_MS = 1756687794173

RUNNER_ZONES = ("UTC", "America/Chicago", "Asia/Tokyo", "Australia/Sydney")


def test_league_date_uses_the_league_clock():
    assert league_date(DRAFT_2025_MS) == "2025-08-31"


def test_league_date_is_identical_across_runner_timezones():
    original = os.environ.get("TZ")
    try:
        rendered = set()
        for zone in RUNNER_ZONES:
            os.environ["TZ"] = zone
            time.tzset()
            rendered.add(league_date(DRAFT_2025_MS))
        # One value, not four: where the pull runs must not reach the output.
        assert rendered == {"2025-08-31"}
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        time.tzset()


def test_league_date_blank_when_timestamp_missing():
    # Sleeper omits `created` on some transaction rows, and `_draft_start` is
    # absent until a draft is scheduled. Both render blank rather than 1970.
    assert league_date(None) == ""
    assert league_date(0) == ""
    assert league_date("") == ""
