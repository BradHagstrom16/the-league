"""Loads the league's pulled CSV data plus the two hand-maintained templates
(`manager_names.csv`, `league_lore.yml`) into a single `LeagueData` bundle.

Every later stats module imports `LeagueData`/`load_data` from here instead of
re-parsing `data/*.csv` itself, so the field names and helper methods on
`LeagueData` are the shared contract for the rest of the site.
"""
from dataclasses import dataclass, field
from pathlib import Path
import csv
import pandas as pd
import yaml

# Sleeper ids are 18-digit numbers that overflow/precision-break float64, so
# every id-like column is forced to str on read. pandas silently ignores dtype
# keys for columns that don't exist in a given CSV.
_DTYPES = {"user_id": str, "player_id": str}


@dataclass
class LeagueData:
    matchups: pd.DataFrame
    drafts: pd.DataFrame
    standings: pd.DataFrame
    player_weeks: pd.DataFrame
    player_points: pd.DataFrame
    transactions: pd.DataFrame
    settings: pd.DataFrame
    managers: pd.DataFrame
    brackets: pd.DataFrame
    names: dict = field(default_factory=dict)
    handles: dict = field(default_factory=dict)
    avatars: dict = field(default_factory=dict)
    lore: dict = field(default_factory=dict)

    def played_seasons(self):
        """Complete seasons only, per settings `status`."""
        s = self.settings
        return sorted(s[s.status.isin(["complete", "in_season", "post_season"])]
                      .season.astype(int).tolist())

    def era(self, season: int) -> str:
        row = self.settings[self.settings.season.astype(int) == int(season)]
        n = int(row.iloc[0]["teams"]) if len(row) else 12
        return f"{n}-team"

    def r2u(self, season: int) -> dict:
        g = self.managers[self.managers.season.astype(int) == int(season)]
        return dict(zip(g.roster_id.astype(int), g.user_id))

    def display(self, user_id: str) -> str:
        return self.names.get(user_id) or self.handles.get(user_id, str(user_id))

    def reg_matchups(self) -> pd.DataFrame:
        """Played regular-season rows, numeric season/week/points, plus
        `user_id`/`opponent_user_id` merged on from `managers`."""
        m = self.matchups.copy()
        for c in ("season", "week", "roster_id", "opponent_roster_id"):
            m[c] = m[c].astype(int)
        for c in ("points", "opponent_points"):
            m[c] = m[c].astype(float)
        if m.is_playoff.dtype == object:
            m["is_playoff"] = m.is_playoff.astype(str).eq("True")
        m = m[~m.is_playoff]
        u = self.managers[["season", "roster_id", "user_id"]].copy()
        u["season"] = u.season.astype(int); u["roster_id"] = u.roster_id.astype(int)
        m = m.merge(u, on=["season", "roster_id"], how="left")
        m = m.merge(u.rename(columns={"roster_id": "opponent_roster_id",
                                      "user_id": "opponent_user_id"}),
                    on=["season", "opponent_roster_id"], how="left")
        return m


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=_DTYPES)


def _load_names(path: Path) -> dict:
    """user_id -> real_name, skipping rows where real_name is blank."""
    if not path.exists():
        return {}
    with open(path, newline="") as f:
        return {
            row["user_id"]: row["real_name"].strip()
            for row in csv.DictReader(f)
            if (row.get("real_name") or "").strip()
        }


def _latest_per_user(managers: pd.DataFrame) -> pd.DataFrame:
    """One row per user_id: the row from the latest season that user appears in."""
    return managers.sort_values("season").groupby("user_id", as_index=False).last()


def _handles_and_avatars(managers: pd.DataFrame) -> tuple[dict, dict]:
    latest = _latest_per_user(managers)
    handles = dict(zip(latest.user_id, latest.manager))
    avatars = dict(zip(latest.user_id, latest.avatar.fillna("")))
    return handles, avatars


def _load_lore(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        loaded = yaml.safe_load(f)
    return loaded or {}


def load_data(base: Path) -> LeagueData:
    """`base` is the repo root: reads `base/data`, `base/manager_names.csv`,
    and `base/league_lore.yml`."""
    base = Path(base)
    data = base / "data"

    managers = _read_csv(data / "managers.csv")
    handles, avatars = _handles_and_avatars(managers)

    return LeagueData(
        matchups=_read_csv(data / "matchups_all.csv"),
        drafts=_read_csv(data / "drafts_all.csv"),
        standings=_read_csv(data / "league_history.csv"),
        player_weeks=_read_csv(data / "player_weeks_all.csv"),
        player_points=_read_csv(data / "player_points_all.csv"),
        transactions=_read_csv(data / "transactions_all.csv"),
        settings=_read_csv(data / "league_settings.csv"),
        managers=managers,
        brackets=_read_csv(data / "brackets_all.csv"),
        names=_load_names(base / "manager_names.csv"),
        handles=handles,
        avatars=avatars,
        lore=_load_lore(base / "league_lore.yml"),
    )


def write_name_template(base: Path) -> None:
    """Create/update `manager_names.csv` with every distinct user_id across
    history. Never overwrites a filled-in real_name."""
    base = Path(base)
    managers = _read_csv(base / "data" / "managers.csv")
    handles, _ = _handles_and_avatars(managers)
    existing = _load_names(base / "manager_names.csv")

    rows = sorted(
        ({"user_id": uid, "handle": handle, "real_name": existing.get(uid, "")}
         for uid, handle in handles.items()),
        key=lambda r: r["handle"],
    )

    with open(base / "manager_names.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "handle", "real_name"])
        writer.writeheader()
        writer.writerows(rows)


_LORE_TEMPLATE = """\
# Hand-maintained league lore. The site renders placeholders until this is filled in.
trophy_name: ""            # what the champion's trophy is called
punishments: {}            # season -> what last place had to do, e.g. 2024: "Ate a ghost pepper"
champion_notes: {}         # season -> one-liner about that title run
"""


if __name__ == "__main__":
    _base = Path(__file__).resolve().parent.parent
    write_name_template(_base)
    _lore_path = _base / "league_lore.yml"
    if not _lore_path.exists():
        _lore_path.write_text(_LORE_TEMPLATE)
