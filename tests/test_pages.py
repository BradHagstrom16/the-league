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
    assert 'class="bracket"' in s25                   # railed ladder, not prose
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
    assert "Hit rate" in draft and "Early-round DNA" in draft
    r1 = payload["drafts"]["by_round"][0]
    assert f"{r1['hit_rate'] * 100:.1f}%" in draft         # hit rate rendered
    assert 'scope="rowgroup"' in draft                     # grouped superflex
    trades = (site / "trades.html").read_text()
    assert "FAAB" in trades
    champs = (site / "champions.html").read_text()
    assert "Wall of Shame" in champs


def test_luck_page(tmp_path, monkeypatch):
    payload, written, site = _built(tmp_path, monkeypatch)
    assert (site / "luck.html") in written
    html = (site / "luck.html").read_text()
    assert "Career all-play" in html
    assert "Biggest heists" in html and "Robbed" in html
    top = max(payload["luck"]["career"], key=lambda r: r["luck_delta"])
    assert f"{top['luck_delta']:+.2f}" in html             # luckiest marquee posts
    h = payload["luck"]["heists"][0]
    assert f"{h['points']:,.2f}" in html                   # heist score, fmt2 parity
    for s in payload["meta"]["seasons"]:                   # one group row per season
        assert f'scope="rowgroup">{s}<' in html
