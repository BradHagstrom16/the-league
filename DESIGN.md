---
name: The League
description: A twelve-manager fantasy football league's six-season record, presented as a Las Vegas sportsbook tote board carrying the league's own purple.
colors:
  board: "#0a0a0d"
  board-raised: "#14121b"
  rail: "#4a3f2e"
  rail-lit: "#8a7347"
  ink: "#e8e6ee"
  ink-dim: "#9a95a8"
  purple-deep: "#481878"
  purple-glow: "#a78bc8"
  amber: "#f5a018"
  silver: "#d1d1d1"
  win: "#58b368"
  loss: "#d4643f"
  chart-purple: "#8f66c9"
  chart-amber: "#c87f1a"
  chart-steel: "#2694c9"
  diverge-neutral: "#3a3743"
typography:
  display:
    fontFamily: "Saira Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(2rem, 6vw, 3rem)"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "0.04em"
  headline:
    fontFamily: "Saira Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(1.8rem, 5vw, 2.6rem)"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "0.05em"
  title:
    fontFamily: "Saira Condensed, Arial Narrow, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.06em"
  label:
    fontFamily: "Saira Condensed, Arial Narrow, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.09em"
  body:
    fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  numeral:
    fontFamily: "Chivo Mono, ui-monospace, monospace"
    fontSize: "0.95rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
rounded:
  none: "0px"
  lamp: "2px"
  soft: "6px"
  full: "50%"
components:
  panel:
    backgroundColor: "{colors.board-raised}"
    rounded: "{rounded.none}"
    padding: "0"
  panel-pad:
    backgroundColor: "{colors.board-raised}"
    rounded: "{rounded.none}"
    padding: "16px"
  marquee:
    backgroundColor: "{colors.board-raised}"
    rounded: "{rounded.none}"
    padding: "16px 20px"
  chip-avatar:
    backgroundColor: "{colors.purple-deep}"
    textColor: "{colors.ink}"
    rounded: "{rounded.full}"
    size: "24px"
  nav-link:
    textColor: "{colors.ink-dim}"
    typography: "{typography.label}"
    padding: "12px 14px 10px"
  nav-link-active:
    textColor: "{colors.amber}"
    typography: "{typography.label}"
    padding: "12px 14px 10px"
---

# Design System: The League ("The Board")

## Overview

**Creative North Star: "The Board"**

The League is a Las Vegas sportsbook tote board that happens to carry the league's own purple. Every stat is a line posted on the board, with receipts, not a metric dropped into a KPI card — the system deliberately refuses the dashboard-tile arrangement common to sports-analytics sites. The board itself is a matte near-black field (`#0a0a0d`), ruled into sections by thin brass rails, with signage set in uppercase Saira Condensed and every number that matters posted in tabular Chivo Mono. Purple appears, but as the house's own tint on heritage and identity elements, not as the headline color — amber is what lights up when a number matters. Stripped of all content, the board should still read as itself: a black board of railed sections awaiting numbers.

The site is built for a group chat that opens it mid-argument, mostly on phones, to settle a bet with a specific number. Density favors legibility of many stat lines over generous whitespace; the aesthetic is a bookkeeper's ledger crossed with a casino tote board, not an editorial magazine. Trash-talk framing is confined to labels, superlatives, and lore copy — table data itself stays plain and rigorous, in line with the product's "receipts, not vibes" principle.

**Key Characteristics:**
- Matte near-black board surface, sectioned by thin brass rails (unlit `#4a3f2e`, lit `#8a7347`)
- Saira Condensed, uppercase and letter-spaced, on every structural label and heading
- Chivo Mono, tabular-nums, carries every number that matters — the system's signature move
- League purple is a heritage/identity accent (avatar fallbacks, links, playoff tint), never the primary attention color — amber owns that role
- Flat, cut-corner geometry throughout; circles are reserved for human identity (avatars, crest)
- No KPI cards or dashboard tiles — every stat is a "posted line" inside a ruled board panel

## Colors

The palette is a near-black field with two accent temperatures — cool brass/purple for structure and identity, warm amber for anything that should win the argument.

### Primary
- **Amber** (`#f5a018`): the number that matters. Used on the hero "posted" figure in every marquee, the active nav tab and its underline, standout ("hot") table values, the champion mark, keeper-round call-outs, focus rings, and list-marker bullets in the rules list. Nothing decorative gets amber — it is reserved for significance.

### Secondary
- **DGN Heritage Purple** (`#481878`): the league's own color, used sparingly — the fallback initial-avatar background, the drop-shadow glow under the draft-room hero crest, and the tint on playoff-week table rows.
- **Purple Glow** (`#a78bc8`): the default link color site-wide (hovers to amber).

### Neutral
- **Board Black** (`#0a0a0d`): the page background — the black field itself.
- **Raised Panel** (`#14121b`): every table, marquee, trade card, and hero panel sits on this one step lighter than the field — the system's entire "elevation" vocabulary.
- **Rail** (`#4a3f2e`) / **Rail Lit** (`#8a7347`): brass dividers. Unlit rail draws quiet hairlines (table cell borders, the board's outer frame); lit rail marks the primary structural edges (nav bottom border, section-heading rule, footer top border).
- **Posted Ink** (`#e8e6ee`): primary text.
- **Dim Ink** (`#9a95a8`): secondary text, table headers, labels, notes.
- **Silver** (`#d1d1d1`): numerals at rest in table cells, before anything makes them "hot."
- **Win** (`#58b368`) / **Loss** (`#d4643f`): the only semantic (non-brass, non-amber) colors — a win/loss result, positive/negative deltas (luck, surplus, margin).

### Chart Palette (separate, validated set)
- **Chart Purple** (`#8f66c9`), **Chart Amber** (`#c87f1a`), **Chart Steel** (`#2694c9`): the fixed categorical order for every line/bar chart, and the low/high ends of the diverging head-to-head heatmap scale (`#8f66c9` → **Diverge Neutral** `#3a3743` at .500 → `#c87f1a`). This is a distinct set from the UI's `amber`/`purple-deep` — deliberately different values, chosen and validated (dataviz six-check) for rendering directly on the `#0a0a0d` board surface. Never substitute the UI amber or heritage purple into a chart, and never the reverse.

### Named Rules
**The Amber Means It Matters Rule.** Amber marks the number, tab, or mark that should win the argument — the hero posted figure, the active nav tab, a hot table value, the champion mark, the focus ring. It never appears as plain decoration.

**The Purple Stays Heritage Rule.** Purple is lineage and navigation, not headline attention: it shows up in avatar fallbacks, link color, and the playoff-week tint — never as a hero number's color or a "hot" highlight.

## Typography

**Display Font:** Saira Condensed (with Arial Narrow, sans-serif fallback)
**Body Font:** system-ui (with -apple-system, Segoe UI, sans-serif fallback)
**Label/Mono Font:** Chivo Mono, a variable font (weights 100–900), used for every numeral

**Character:** A signage face paired with a ledger face. Saira Condensed, always uppercase and letter-spaced, does the announcing (headings, nav, labels); Chivo Mono, always tabular, does the posting (every score, percentage, dollar figure, streak). The system-ui body font only ever carries prose — it never carries a number.

### Hierarchy
- **Display** (700, `clamp(2rem, 6vw, 3rem)`, line-height 1.1): the draft-room hero headline ("The Draft Room is open") — rare, appears only in that one seasonal state.
- **Headline** (700, `clamp(1.8rem, 5vw, 2.6rem)`, line-height 1.15): the page title (`.page-title`), one per interior page.
- **Title** (700, 1.5rem fixed, line-height 1.2): the section heading (`.section > h2`), the board's workhorse header, always paired with a brass rule trailing off to the right.
- **Body** (400, 1rem, line-height 1.55): paragraph and note copy; notes cap at `72ch`.
- **Label** (600, ~0.72–0.95rem depending on context, letter-spacing 0.08–0.1em, uppercase): nav tabs, table headers, marquee line-names, `h3` sub-headings, the champion mark. Always uppercase; never mixed case.
- **Numeral** (Chivo Mono, tabular-nums; scales from 0.95rem in table cells to `clamp(2rem, 6vw, 3.2rem)` in a hero marquee): the system's signature type role. Every score, percentage, dollar amount, and streak renders here, in silver at rest, amber when it's the number that matters.

### Named Rules
**The Tabular Numerals Rule.** Every quantity — scores, win percentages, dollars, streaks, deltas — renders in Chivo Mono with `font-variant-numeric: tabular-nums`. The body sans-serif never carries a number.

**The Signage Caps Rule.** Every structural label — nav tabs, table headers, section titles, line-names — is Saira Condensed, uppercase, letter-spaced. Lowercase, mixed-case text is reserved for body prose and player/manager names.

## Layout

`main` is a single centered column, `max-width: 72rem`, framed by a 1px rail border on the sides and top only — the frame stays open at the bottom, so the board reads as a surface the content sits on rather than a closed card. Sections stack with a 40px top margin and a heading rule; panels and marquees use a tighter 12–24px internal rhythm; the page closes with 64px of bottom padding before the footer rail.

Three sticky layers keep context in view while scrolling a long board: the nav bar (`position: sticky; top: 0`), each table's header row, and each table's first column (identity — manager or week — stays "posted" while the rest of the row scrolls under it). Tables that overflow horizontally get a brass-tinted scroll cue (a radial glow plus a linear cover) baked into the panel's background at both edges; on the left edge this cue sits behind the sticky first column by design — the posted column is itself the "there's more here" signal, not a bug to fix.

Two grid utilities cover paired content: `.two-up` (`repeat(auto-fit, minmax(280px, 1fr))`) for paired marquees/panels like champion vs. shame, and `.two-col` (`repeat(auto-fit, minmax(320px, 1fr))`) for longer two-column spreads (Hall of Champions vs. Wall of Shame, steals vs. busts). At 640px the masthead tightens, the tagline hides, the wordmark shrinks, and table cell padding drops — mobile is the primary target, not an afterthought, per the site's group-chat audience.

## Elevation & Depth

The board is flat by design: no card, panel, or table casts a structural shadow, and every container uses `border-radius: 0`. Depth comes from a single tone step — board (`#0a0a0d`) to raised panel (`#14121b`) — plus brass rail borders, never from `box-shadow` lift. The only shadow-family effects in the system are glows, and they mean "lit," not "elevated": a soft amber text-shadow behind the hero posted number, small amber/loss-colored glow dots on marquee and champion-mark indicator lamps, and a purple-tinted `drop-shadow` under the draft-room hero crest.

### Named Rules
**The No-Lift Rule.** Surfaces never gain a shadow from being a card or being hovered. The only shadows that exist are glows on things that are already "lit" — the posted hero number, the indicator lamps, the crest.

## Shapes

Radius is 0 by law: every board panel, marquee, trade card, and page-furniture block is square-cut. Two identity elements break the rule with a full circle (`border-radius: 50%`) — Sleeper avatars and the crest mark — because a person's photo is the one thing the board renders as anything other than a rule or a number. Two smaller, explicit exceptions exist: the 2px-radius indicator lamp (the small lit dot before a marquee line-name or the champion mark) and the 6px-radius stat-strip container on manager pages, which fuses its grid of career tiles into one soft-edged unit instead of reading as separate cut panels. Borders follow the same logic as rails: 1px hairlines (`--rail`, or the darker `#1c1922`) divide table cells and rows and frame the board itself; 2px `--rail-lit` marks the handful of primary structural edges (nav's bottom border, footer's top border); a single 1px amber left-border marks the winning side of a trade ledger entry.

## Components

### Board Panel / Table (signature)
The board's core unit — every stat set lives in a sortable table inside a raised, square-cut panel.
- **Shape:** `border-radius: 0`, 1px rail border, background `#14121b`.
- **Header:** sticky, uppercase Saira Condensed labels in dim ink, 1px lit-rail bottom border.
- **First column:** sticky left, so a row's identity (manager, week) stays posted while the rest scrolls — the board's substitute for a visible left-edge scroll cue.
- **Sortable variant:** clickable `th`, cursor pointer, an amber ▲/▼ appended via CSS to the active sort column (`assets/js/tables.js` drives the click behavior — numeric-aware, no external library).
- **Cell states:** numerals right-align in tabular Chivo Mono, silver at rest; `.hot` bumps to amber/600-weight for a standout value; `.pos`/`.neg` recolor to win-green/loss-rust; row hover tints to `#171420`.

### Manager Chip
The identity unit — appears identically whether in a table cell, a marquee, or a page header.
- **Style:** a circular 24px Sleeper avatar (or a purple-deep initial-in-circle fallback when no avatar exists) plus the manager's linked name; an optional 3-digit "rot" (rotation) number in small tracked mono precedes it.
- **Scale:** the same shape scales to 40px in a marquee's posted figure and 72px on a manager's own page header — the chip never changes proportion or shape, only size.

### Marquee / Posted Line
The hero-stat unit — the number a page most wants screenshotted.
- **Shape:** flat raised panel, `border-radius: 0`, 16–20px padding.
- **Label:** a tracked uppercase line-name preceded by a 2px-radius "lamp" — amber-glow for a normal posted line, loss-red-glow for a `.shame` variant.
- **Value:** the number itself renders at hero scale (`clamp(2rem, 6vw, 3.2rem)`) in amber Chivo Mono with a soft amber text-shadow glow — the one place text visibly "lights up."
- **`.posted-line` variant:** label left, number right on ≥760px viewports, for record-book-style single-line entries.

### Stat Strip
A fused row of small posted numbers for a manager's career summary.
- **Shape:** the system's one 6px-radius container, tiles separated by 2px rail-colored gutters rather than borders.
- **Cell:** tracked uppercase label over a `posted-sm` value (1.3rem Chivo Mono); a `.gold` class turns a value amber (titles).

### Navigation
Sticky `board-nav` bar beneath the masthead. Tabs are uppercase Saira Condensed, dim ink at rest, amber text with a 3px amber underline when active (`aria-current="page"`); the bar horizontal-scrolls on narrow viewports rather than wrapping to a second row.

### Champion / Shame Mark
An inline uppercase label carrying a 2px-radius glow lamp (amber for champion, loss-red for shame) in place of an emoji or icon — the board's own comment on this pattern is literal: "a lamp, not an emoji."

## Do's and Don'ts

### Do:
- **Do** route every number — score, percentage, dollar amount, streak, delta — through Chivo Mono with `tabular-nums`; the body sans-serif never carries a number.
- **Do** set every structural label in uppercase, letter-spaced Saira Condensed (nav, table headers, section titles, line-names).
- **Do** reserve amber for the value that matters (hot cells, the champion mark, the active nav tab, the hero posted number, focus rings) — never as plain decoration.
- **Do** keep the categorical chart order fixed at purple → amber → steel (`#8f66c9`, `#c87f1a`, `#2694c9`) and the H2H heatmap on the purple/`#3a3743`-neutral/amber diverging scale; label series directly and print the value inside every heatmap cell rather than relying on color alone.
- **Do** keep every panel, marquee, and card square (`border-radius: 0`); reserve circles for avatars/crest and the two named exceptions (2px lamps, the 6px stat-strip).

### Don't:
- **Don't** add a `box-shadow`-based lifted/hover-elevated card. Depth here is the board-to-raised-panel tone step plus a rail border, not a shadow; the only shadows that exist are "lit" glows.
- **Don't** substitute the UI's amber (`#f5a018`) or heritage purple (`#481878`) into a chart, or vice versa — the chart palette is a separate, validated set (`#8f66c9`/`#c87f1a`/`#2694c9`) tuned for the `#0a0a0d` surface.
- **Don't** add buttons, form inputs, or filter/selectable chips — none exist in the shipped system. Every action is a link or a click on a sortable table header.
- **Don't** treat a "hot" highlight on a leaderboard column as an exact top-N count. The board flags standout values (e.g. the highest win percentages), and ties can widen that set beyond a fixed number — document it as "the standout values," not "the top 3."
- **Don't** cover the sticky first table column's role: it is the left-edge scroll cue's replacement by design, not a rendering bug to patch.
