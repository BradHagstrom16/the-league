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
