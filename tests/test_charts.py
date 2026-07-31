from leaguestats.charts import svg_bar, svg_heatmap, svg_line


def test_svg_line_basic():
    svg = svg_line([("Al", [1, 3, None, 2])], ["21", "22", "23", "24"], y_invert=True)
    assert svg.startswith("<svg") and 'class="series"' in svg
    assert svg.count('class="pt"') == 3          # None week draws no point


def test_svg_line_multi_series_direct_labels():
    svg = svg_line([("Al", [10, 20]), ("Bo", [5, 15])], ["w1", "w2"])
    assert svg.count('class="series"') == 2
    assert "Al" in svg and "Bo" in svg           # direct end labels


def test_svg_bar():
    svg = svg_bar([("Al", 10.0), ("Bo", 25.5)], highlight="Bo")
    assert svg.startswith("<svg") and svg.count('class="bar"') == 2
    assert "25.5" in svg


def test_svg_heatmap_skips_none():
    svg = svg_heatmap(["a"], ["b"], {("a", "b"): None})
    assert "<svg" in svg and "rect" in svg


def test_svg_heatmap_values_and_titles():
    svg = svg_heatmap(["a", "b"], ["a", "b"],
                      {("a", "b"): 0.75, ("b", "a"): 0.25})
    assert svg.count("<title>") >= 2
