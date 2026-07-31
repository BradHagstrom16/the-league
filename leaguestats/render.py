"""Jinja2 environment, page writer, and slug helper for the static site."""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

_env = None


def env() -> Environment:
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(str(TEMPLATES)),
            autoescape=select_autoescape(["html", "j2"]),
        )
        _env.filters["fmt2"] = lambda x: f"{x:,.2f}"
        _env.filters["fmt0"] = lambda x: f"{x:,.0f}"
        _env.filters["pct"] = lambda x: f"{x * 100:.1f}%"
    return _env


def slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]", "-", str(s).lower())).strip("-")


def render_page(template: str, ctx: dict, out_path: Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(env().get_template(template).render(**ctx))
