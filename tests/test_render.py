from leaguestats.render import render_page, slug


def test_slug():
    assert slug("KingTowsk") == "kingtowsk"
    assert slug("Jack Taco 98!") == "jack-taco-98"


def test_render_page(tmp_path):
    out = tmp_path / "x.html"
    render_page("base.html.j2", {"root": "", "meta": {"league_name": "The League"}}, out)
    html = out.read_text()
    assert "<nav" in html and "records.html" in html
    assert "impeccable" not in html.lower()      # no tooling leakage
    assert "THESIS" in html                      # direction contract survives render
