import build_site


def _built(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "SITE", tmp_path)
    monkeypatch.setattr(build_site, "SITE_DATA", tmp_path / "data")
    payload = build_site.build_json()
    written = build_site.build_pages(payload)
    return payload, written, tmp_path


def test_pages_render(tmp_path, monkeypatch):
    payload, written, site = _built(tmp_path, monkeypatch)
    idx = (site / "index.html").read_text()
    assert "The league" in idx
    champs = [s["champion_name"] for s in payload["career"]["seasons"]]
    assert champs[-1] in idx                      # reigning champion on home page
    s25 = (site / "seasons" / "2025.html").read_text()
    assert "Weekly results" in s25 and "Bracket" in s25
    assert (site / "records.html").exists()
    assert all(p.exists() for p in written)


def test_manager_and_h2h_pages(tmp_path, monkeypatch):
    payload, written, site = _built(tmp_path, monkeypatch)
    pages = list((site / "managers").glob("*.html"))
    assert len(pages) >= 12                        # every manager in history
    one = pages[0].read_text()
    assert "Career" in one and "Head-to-head" in one
    h2h = (site / "h2h.html").read_text()
    assert "-vs-" in h2h and "<svg" in h2h


def test_remaining_pages(tmp_path, monkeypatch):
    payload, written, site = _built(tmp_path, monkeypatch)
    draft = (site / "draft.html").read_text()
    assert "Keeper rules" in draft and "keepers charged" in draft
    trades = (site / "trades.html").read_text()
    assert "FAAB" in trades
    champs = (site / "champions.html").read_text()
    assert "Wall of Shame" in champs
