"""
Hand-built SVG charts for The Board.

Every chart renders on the board's near-black surface. Data colors are the
validated categorical set (purple, amber, steel — fixed order, never cycled;
dataviz validator: all six checks pass on #0a0a0d). Identity never rides on
color alone: series get direct end labels, heatmap cells carry their number.
"""

from html import escape

# Fixed categorical order — a 4th series is a design smell, not a new hue.
CATEGORICAL = ["#8f66c9", "#c87f1a", "#2694c9"]
GRID = "#26232e"
AXIS_INK = "#9a95a8"
SURFACE = "#0a0a0d"
DIVERGE_LOW = (0x8F, 0x66, 0xC9)    # purple — they own you
DIVERGE_MID = (0x3A, 0x37, 0x43)    # neutral at .500
DIVERGE_HIGH = (0xC8, 0x7F, 0x1A)   # amber — you're the house

PAD_L, PAD_R, PAD_T, PAD_B = 44, 110, 14, 30


def _scale(vmin, vmax, lo, hi):
    span = (vmax - vmin) or 1.0
    return lambda v: lo + (v - vmin) / span * (hi - lo)


def svg_line(series, x_labels, *, w=640, h=280, y_invert=False):
    """Multi-series line chart. None values are gaps. Direct labels at line
    ends; markers carry <title> tooltips."""
    vals = [v for _, ys in series for v in ys if v is not None]
    if not vals:
        return f'<svg viewBox="0 0 {w} {h}" role="img"></svg>'
    vmin, vmax = min(vals), max(vals)
    if y_invert:
        vmin, vmax = vmax, vmin
    sx = _scale(0, max(len(x_labels) - 1, 1), PAD_L, w - PAD_R)
    sy = _scale(vmin, vmax, h - PAD_B, PAD_T)

    out = [f'<svg viewBox="0 0 {w} {h}" role="img" class="chart chart-line" '
           f'preserveAspectRatio="xMidYMid meet">']
    # y ticks: low / mid / high of the value range, recessive.
    lo_v, hi_v = min(vals), max(vals)
    mid_v = (lo_v + hi_v) / 2
    for tv in {lo_v, round(mid_v, 1), hi_v}:
        ty = sy(tv)
        lab_v = f"{tv:g}"
        out.append(f'<line x1="{PAD_L}" y1="{ty:.1f}" x2="{w - PAD_R}" '
                   f'y2="{ty:.1f}" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{PAD_L - 8}" y="{ty + 4:.1f}" class="tick" '
                   f'text-anchor="end">{lab_v}</text>')
    # Recessive grid: one line per x tick.
    for i, lab in enumerate(x_labels):
        x = sx(i)
        out.append(f'<line x1="{x:.1f}" y1="{PAD_T}" x2="{x:.1f}" '
                   f'y2="{h - PAD_B}" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="{h - 10}" class="tick" '
                   f'text-anchor="middle">{escape(str(lab))}</text>')
    for si, (name, ys) in enumerate(series):
        color = CATEGORICAL[si % len(CATEGORICAL)] if len(series) <= 3 else AXIS_INK
        pts = [(sx(i), sy(v)) for i, v in enumerate(ys) if v is not None]
        segs, seg = [], []
        for i, v in enumerate(ys):
            if v is None:
                if seg:
                    segs.append(seg)
                seg = []
            else:
                seg.append((sx(i), sy(v)))
        if seg:
            segs.append(seg)
        out.append(f'<g class="series" data-name="{escape(str(name))}">')
        for s in segs:
            path = " ".join(f"{x:.1f},{y:.1f}" for x, y in s)
            out.append(f'<polyline points="{path}" fill="none" '
                       f'stroke="{color}" stroke-width="2"/>')
        for i, v in enumerate(ys):
            if v is None:
                continue
            x, y = sx(i), sy(v)
            out.append(f'<circle class="pt" cx="{x:.1f}" cy="{y:.1f}" r="4" '
                       f'fill="{color}"><title>{escape(str(name))} · '
                       f'{escape(str(x_labels[i]))}: {v}</title></circle>')
        if pts:
            lx, ly = pts[-1]
            out.append(f'<text x="{lx + 8:.1f}" y="{ly + 4:.1f}" class="end-label" '
                       f'fill="{color}">{escape(str(name))}</text>')
        out.append("</g>")
    out.append("</svg>")
    return "".join(out)


def svg_bar(items, *, w=640, h=280, highlight=None):
    """Vertical bars, 4px rounded data-end, 2px surface gaps, value labels."""
    if not items:
        return f'<svg viewBox="0 0 {w} {h}" role="img"></svg>'
    vmax = max(v for _, v in items) or 1.0
    n = len(items)
    slot = (w - PAD_L - 16) / n
    bar_w = max(slot - 8, 6)
    sy = _scale(0, vmax, h - PAD_B, PAD_T + 14)
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" class="chart chart-bar" '
           f'preserveAspectRatio="xMidYMid meet">']
    out.append(f'<line x1="{PAD_L}" y1="{h - PAD_B}" x2="{w - 8}" '
               f'y2="{h - PAD_B}" stroke="{GRID}" stroke-width="1"/>')
    for i, (name, v) in enumerate(items):
        x = PAD_L + 4 + i * slot
        y = sy(v)
        color = "#c87f1a" if (highlight is not None and name == highlight) else "#8f66c9"
        bh = max(h - PAD_B - y, 1)
        out.append(f'<g class="bar" data-name="{escape(str(name))}">'
                   f'<path d="M{x:.1f},{h - PAD_B} v{-(bh - 4):.1f} '
                   f'q0,-4 4,-4 h{bar_w - 8:.1f} q4,0 4,4 v{bh - 4:.1f} z" '
                   f'fill="{color}"><title>{escape(str(name))}: {v}</title></path>'
                   f'<text x="{x + bar_w / 2:.1f}" y="{y - 6:.1f}" class="bar-val" '
                   f'text-anchor="middle">{v:g}</text>'
                   f'<text x="{x + bar_w / 2:.1f}" y="{h - 10}" class="tick" '
                   f'text-anchor="middle">{escape(str(name))}</text></g>')
    out.append("</svg>")
    return "".join(out)


def _diverge(t):
    """0..1 -> hex on the purple/neutral/amber diverging scale (mid 0.5)."""
    t = min(max(t, 0.0), 1.0)
    if t < 0.5:
        a, b, f = DIVERGE_LOW, DIVERGE_MID, t / 0.5
    else:
        a, b, f = DIVERGE_MID, DIVERGE_HIGH, (t - 0.5) / 0.5
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * f) for i in range(3))


def svg_heatmap(row_labels, col_labels, values, *, cell=40, fmt="{:.0f}"):
    """Matrix heatmap with 2px gaps; None cells stay surface-colored.
    Values are 0..1 win pcts colored on the diverging scale."""
    lab_w, lab_h = 110, 84
    w = lab_w + len(col_labels) * cell + 40   # room for the last rotated label
    h = lab_h + len(row_labels) * cell + 4
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" class="chart chart-heat" '
           f'preserveAspectRatio="xMidYMid meet">']
    for j, cl in enumerate(col_labels):
        cx = lab_w + j * cell + cell / 2
        out.append(f'<text x="{cx:.0f}" y="{lab_h - 10}" class="tick" '
                   f'text-anchor="start" transform="rotate(-55 {cx:.0f} '
                   f'{lab_h - 10})">{escape(str(cl))}</text>')
    for i, rl in enumerate(row_labels):
        y = lab_h + i * cell
        out.append(f'<text x="{lab_w - 8}" y="{y + cell / 2 + 4:.0f}" class="tick" '
                   f'text-anchor="end">{escape(str(rl))}</text>')
        for j, cl in enumerate(col_labels):
            x = lab_w + j * cell
            v = values.get((rl, cl))
            if v is None:
                out.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cell - 2}" '
                           f'height="{cell - 2}" rx="3" fill="{SURFACE}" '
                           f'stroke="{GRID}"/>')
                continue
            fill = _diverge(v)
            # Dark ink only where the fill is truly light (both scale ends);
            # mid-tones keep light ink to clear the 4.5:1 floor.
            ink = "#0a0a0d" if (v >= 0.85 or v <= 0.15) else "#e8e6ee"
            out.append(f'<g class="cell"><rect x="{x + 1}" y="{y + 1}" '
                       f'width="{cell - 2}" height="{cell - 2}" rx="3" '
                       f'fill="{fill}"><title>{escape(str(rl))} vs '
                       f'{escape(str(cl))}: {v:.3f}</title></rect>'
                       f'<text x="{x + cell / 2:.0f}" y="{y + cell / 2 + 4:.0f}" '
                       f'class="cell-val" fill="{ink}" text-anchor="middle">'
                       f'{escape(fmt.format(v * 100))}</text></g>')
    out.append("</svg>")
    return "".join(out)
