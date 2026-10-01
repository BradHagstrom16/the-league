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


def test_finish_on_an_in_progress_season_is_flagged(tmp_path):
    import shutil, csv
    shutil.copytree(BASE, tmp_path / "data")
    data = tmp_path / "data"
    settings = list(csv.DictReader(open(data / "league_settings.csv")))
    for r in settings:
        if r["season"] == "2026":
            r["status"] = "in_season"
    with open(data / "league_settings.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=settings[0].keys())
        w.writeheader(); w.writerows(settings)
    p = data / "standings" / "standings_2026.csv"
    rows = list(csv.DictReader(open(p)))
    rows[0]["finish"] = "1"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    failures = v.check_no_finish_for_unplayed(data)
    assert any("2026" in f and "in_season" in f for f in failures)

def test_aggregates_catches_corruption(tmp_path):
    import shutil, csv
    shutil.copytree(BASE, tmp_path / "data")
    p = tmp_path / "data" / "matchups_all.csv"
    rows = list(csv.DictReader(open(p)))
    rows.pop(0)
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    failures = v.run_checks(tmp_path / "data")
    assert any("matchups_all.csv" in f for f in failures)
