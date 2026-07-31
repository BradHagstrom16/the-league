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
