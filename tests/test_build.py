import json

import numpy as np

from leaguestats.util import to_jsonable


def test_to_jsonable():
    obj = {"a": np.int64(3), "b": [np.float64(1.5)], np.int64(2024): {"c": np.bool_(True)}}
    assert json.dumps(to_jsonable(obj)) == '{"a": 3, "b": [1.5], "2024": {"c": true}}'


def test_full_build_on_real_data(tmp_path, monkeypatch):
    import build_site
    monkeypatch.setattr(build_site, "SITE_DATA", tmp_path)
    build_site.build_json()
    for name in ("career", "h2h", "luck", "lineups", "drafts",
                 "keepers", "transactions", "records", "meta"):
        payload = json.loads((tmp_path / f"{name}.json").read_text())
        assert payload, name
