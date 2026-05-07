"""Render a Report to a single self-contained HTML document.

Redesigned single-page layout, US Letter, weasyprint-friendly. The page is
split into four labelled sections — Foundation (pH/CEC/OM), Macronutrients,
Micronutrients, Contaminants — with a header band, an at-a-glance summary
strip, and a brand footer.

Nutrient rows use a 5-zone "sweet spot in the middle" track with a numeric
scale rendered beneath, plus a tier word (e.g. "Optimal", "Critically low").
Toxic-metal rows (Al, Pb) get their own visual: a one-direction status pill
("OK" / "ELEVATED") because "lower is better" makes a symmetric scale
semantically wrong.

All bar / icon visuals are inline SVG with presentation attributes — class-
selector CSS is ignored by weasyprint inside nested SVG, so colors and
strokes are inlined.

Determinism contract
--------------------
This module is pure string concatenation with no time/random/uuid/tempfile
calls. Every collection it iterates is a tuple in source order
(``SPECS``, ``TOXICS``, ``SECTIONS``, ``ClassifiedSample.nutrients``); the
small dicts (``_TIER_LABEL``, ``_ICON_SPECS``, ``_SHORT``) are only used for
keyed lookup, never iterated. Combined with ``pipeline._DETERMINISTIC_SOURCE_DATE_EPOCH``
on the weasyprint side, identical inputs produce byte-identical HTML and PDF.
"""

from __future__ import annotations

import base64
from functools import cache
from html import escape
from pathlib import Path

from .models import ClassifiedSample, Report, Tier, TieredValue
from .thresholds import (
    SPEC_BY_LABEL,
    ThresholdSpec,
    ToxicSpec,
    tier_to_zone_index,
    toxic_lookup,
    zone_numeric_ranges,
)

_ASSETS = Path(__file__).parent / "assets"


@cache
def _logo_data_uri(name: str) -> str:
    data = (_ASSETS / name).read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


# Symbol glyphs for inline icons (rendered as SVG).
_ICON_SPECS: dict[Tier, tuple[str, str, str]] = {
    # tier -> (glyph, bg, fg)
    Tier.VERY_LOW: ("!", "#b03a2e", "#ffffff"),
    Tier.LOW: ("•", "#c98226", "#ffffff"),
    Tier.GOOD: ("✓", "#4f7a3a", "#ffffff"),
    Tier.HIGH: ("•", "#c98226", "#ffffff"),
    Tier.VERY_HIGH: ("!", "#b03a2e", "#ffffff"),
}

# Five-zone fill colors (left → right). Symmetric red-amber-green-amber-red.
ZONE_FILLS = ("#e9c8c2", "#efd9b3", "#c5d6ad", "#efd9b3", "#e9c8c2")
INK = "#1c1c1c"
PAPER = "#fbfaf6"

# Tier → human label + color class.
_TIER_LABEL: dict[Tier, tuple[str, str]] = {
    Tier.VERY_LOW: ("Critically low", "bad"),
    Tier.LOW: ("Below optimal", "warn"),
    Tier.GOOD: ("Optimal", "good"),
    Tier.HIGH: ("Above optimal", "warn"),
    Tier.VERY_HIGH: ("Excessive", "bad"),
}
# For inverted-direction nutrients, semantic labels stay correct because tier
# is computed from the raw value with direction already applied — see
# thresholds.tier_for. The label table above uses "low/high" purely
# conventionally; the tier itself is the source of truth.

CSS = """
@page { margin: 0; size: Letter; }
:root {
  --brand-green: #1f3a26;
  --brand-green-dark: #16291b;
  --paper: #fbfaf6;
  --paper-2: #f3f0e7;
  --ink: #1c1c1c;
  --ink-soft: #5a5a5a;
  --muted: #8a8579;
  --rule: #e2dccb;
  --good: #4f7a3a;
  --warn: #c98226;
  --bad: #b03a2e;
}
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 10.5px;
  line-height: 1.35;
}
@media screen {
  body { background: #ddd5c2; padding: 24px 0; }
  .page {
    width: 8.5in; min-height: 11in;
    margin: 0 auto;
    background: var(--paper);
    box-shadow: 0 2px 24px rgba(0,0,0,0.12);
    display: flex; flex-direction: column;
  }
}
@media print {
  html, body { background: var(--paper); margin: 0; padding: 0; height: 100%; }
  .page {
    width: 8.5in;
    /* Use exact height (not min-height) so the absolute-positioned footer
       reaches the actual paper edge — min-height lets the box shrink to
       content height, which leaves a paper-colored gap below the band. */
    height: 11in;
    background: var(--paper);
    /* Footer is positioned absolutely in print so weasyprint reliably
       paints its dark-green band at the bottom edge of the page. The
       flex `margin-top: auto` trick doesn't survive weasyprint's page
       layout — the footer gets clipped or loses its background. Reserve
       ~76px of bottom padding so the last data row never collides with
       the absolute-positioned footer block. */
    padding-bottom: 76px;
    position: relative;
    display: block;
    overflow: hidden;
  }
  .foot-block {
    position: absolute;
    left: 0;
    right: 0;
    /* Anchored slightly above the absolute page edge so weasyprint never
       clips the band against the printable-area boundary. */
    bottom: 0;
    /* Re-declare the dark green background on the wrapper so weasyprint
       paints the band even if a child's background gets dropped during
       page-break rasterization. */
    background: var(--brand-green-dark);
  }
  .foot {
    /* Force the print engine to actually fill this band — some PDF
       backends drop CSS backgrounds on `display: grid` elements unless
       `print-color-adjust: exact` is set explicitly. */
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    background: var(--brand-green) !important;
  }
  .subfoot {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    background: var(--brand-green-dark) !important;
  }
}

/* Header */
.hdr {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 18px;
  padding: 16px 36px 12px 36px;
  border-bottom: 1px solid var(--rule);
}
.hdr .logo { height: 34px; width: auto; display: block; }
.hdr .meta {
  text-align: right;
  font-size: 9px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  line-height: 1.5;
}
.hdr .meta b { color: var(--ink); font-weight: 600; }

/* Title */
.title-row {
  padding: 16px 36px 12px 36px;
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: end;
  gap: 24px;
}
.eyebrow {
  font-size: 9px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--brand-green);
  font-weight: 600;
  margin: 0 0 5px 0;
}
h1.title {
  font-family: Georgia, "Times New Roman", serif;
  font-weight: 400;
  font-size: 30px;
  line-height: 1.05;
  letter-spacing: -0.01em;
  margin: 0;
  color: var(--ink);
}
h1.title em { font-style: italic; color: var(--brand-green); }
.subtitle {
  margin: 5px 0 0 0;
  color: var(--ink-soft);
  font-size: 11px;
  max-width: 60ch;
}
.sample-tag {
  display: inline-flex;
  align-items: baseline;
  gap: 7px;
  background: var(--brand-green);
  color: var(--paper);
  padding: 7px 12px;
  font-size: 9px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  white-space: nowrap;
}
.sample-tag b { font-size: 12px; letter-spacing: 0.04em; font-weight: 700; }
.sample-tags { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }

/* Summary strip */
.summary {
  margin: 4px 36px 14px 36px;
  display: grid;
  grid-template-columns: 1.5fr 1fr 1fr 1fr;
  border: 1px solid var(--rule);
  background: var(--paper-2);
}
.summary .cell {
  padding: 10px 12px;
  border-right: 1px solid var(--rule);
}
.summary .cell:last-child { border-right: 0; }
.summary .lbl {
  font-size: 8.5px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 3px;
}
.summary .val {
  font-family: Georgia, serif;
  font-size: 20px;
  line-height: 1.05;
  font-weight: 400;
  color: var(--ink);
}
.summary .val .unit {
  font-size: 10px;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  color: var(--muted);
  margin-left: 3px;
  letter-spacing: 0.05em;
}
.summary .lead h3 {
  margin: 0 0 4px 0;
  font-size: 12px;
  font-weight: 700;
}
.summary .lead p {
  margin: 0;
  font-size: 10px;
  color: var(--ink-soft);
  line-height: 1.4;
}
.summary .lead .head {
  display: flex; align-items: center; gap: 7px;
}
.summary .dot {
  display: inline-block;
  width: 7px; height: 7px; border-radius: 50%;
}
.summary .dot.good { background: var(--good); }
.summary .dot.warn { background: var(--warn); }
.summary .dot.bad { background: var(--bad); }

/* Section */
.section {
  padding: 0 36px;
  margin-bottom: 6px;
}
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 2px;
  margin-bottom: 3px;
}
/* In dual-sample mode, sections sit under a single shared column band so
   each section's underline can be lighter and tighter — the column band
   already carries the strong rule. */
.dual-mode .section { margin-bottom: 4px; }
.dual-mode .row { padding: 3px 0; }
.dual-mode .bar-wrap { height: 20px; }
.dual-mode .bar-scale { font-size: 7px; }
.section-head .h {
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--ink);
}

/* Row */
.row {
  display: grid;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
  border-bottom: 1px solid var(--rule);
}
.row:last-child { border-bottom: 0; }
.row.single { grid-template-columns: 20px 130px 56px 1fr 88px; }
.row.dual   { grid-template-columns: 20px 130px 56px 1fr 56px 1fr; }

/* Single column-header band rendered once at the top of the data area
   (between the summary strip and the first section) when comparing two
   samples. Sticks to the page edge so column ownership is established
   before any data row is read. */
.col-band {
  display: grid;
  grid-template-columns: 20px 130px 56px 1fr 56px 1fr;
  align-items: end;
  gap: 10px;
  margin: 0 36px 6px 36px;
  padding: 5px 0 4px 0;
  border-bottom: 1.5px solid var(--ink);
}
.col-band .col-name {
  grid-column: span 2;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink);
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.col-band .col-name.a { grid-column: 3 / span 2; }
.col-band .col-name.b { grid-column: 5 / span 2; }
.col-band .col-name .swatch {
  display: inline-block;
  width: 9px; height: 9px;
  border-radius: 50%;
  vertical-align: 1px;
}
.col-band .col-name.a .swatch { background: var(--brand-green); }
.col-band .col-name.b .swatch { background: #b8742a; }
.col-band .col-name .nm {
  font-family: Georgia, serif;
  font-style: italic;
  font-weight: 400;
  font-size: 12px;
  letter-spacing: 0;
  text-transform: none;
  color: var(--ink);
}

/* Header row that appears once per page in dual-sample mode, labelling
   the two value+bar column pairs. Aligns with `.row.dual` columns. */
.dual-header {
  display: grid;
  grid-template-columns: 20px 130px 56px 1fr 56px 1fr;
  align-items: end;
  gap: 10px;
  padding: 4px 0 2px 0;
  border-bottom: 1.5px solid var(--ink);
  margin-bottom: 4px;
}
.dual-header .sample-col {
  grid-column: span 2;
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 9px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--ink);
  border-left: 3px solid var(--brand-green);
  padding-left: 8px;
}
.dual-header .sample-col.col-b { border-left-color: var(--warn); }
.dual-header .sample-col .nm {
  font-family: Georgia, serif;
  font-style: italic;
  font-weight: 400;
  font-size: 12px;
  letter-spacing: 0;
  text-transform: none;
  color: var(--ink-soft);
}
/* Dual-sample value tier colors. Apply ONLY in the dual context so the
   single-sample value retains the default ink color. */
.row.dual .val.good { color: var(--good); }
.row.dual .val.warn { color: var(--warn); }
.row.dual .val.bad  { color: var(--bad); }

.row .name { font-weight: 600; font-size: 11px; color: var(--ink); }
.row .name .sub {
  display: block;
  font-weight: 400;
  font-size: 8.5px;
  color: var(--muted);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-top: 1px;
}
.row .val {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  font-size: 13px;
  text-align: right;
  font-family: Georgia, serif;
}
.row .tier {
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  text-align: right;
  font-weight: 700;
}
.row .tier.good { color: var(--good); }
.row .tier.warn { color: var(--warn); }
.row .tier.bad  { color: var(--bad); }

.icon-svg { display: inline-block; width: 18px; height: 18px; }

/* Bar */
.bar-wrap { position: relative; width: 100%; height: 22px; }
.bar-svg {
  position: absolute; top: 4px; left: 0;
  width: 100%; height: 6px;
  display: block;
}
.bar-marker {
  position: absolute;
  top: 0;
  width: 10px;
  height: 14px;
  transform: translateX(-50%);
  pointer-events: none;
}
.bar-marker svg { display: block; width: 10px; height: 14px; }
.bar-scale {
  position: absolute;
  top: 12px; left: 0; right: 0;
  display: flex;
  justify-content: space-between;
  font-size: 7.5px;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.04em;
}

/* Toxic pill — green OK / red Elevated. Lower is always better, so a
   symmetric zone scale is semantically wrong; a chip reads in one glance. */
.toxic-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 11px;
  font-size: 10.5px;
  line-height: 1.2;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.toxic-pill--ok {
  background: #e3ecd8;
  color: #3d5a28;
}
.toxic-pill--elevated {
  background: #f3d7d2;
  color: #7a2019;
}
.toxic-pill__value {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  font-family: Georgia, serif;
  font-size: 12px;
}
.pill-unit {
  text-transform: none;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-weight: 400;
  font-size: 10px;
}

/* Footer */
.foot-block { margin-top: auto; }
.foot {
  background: var(--brand-green);
  color: var(--paper);
  padding: 12px 36px 10px 36px;
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 24px;
}
.foot img.logo-w { height: 24px; }
.foot .contact {
  font-size: 9px;
  letter-spacing: 0.05em;
  text-align: right;
  line-height: 1.55;
  color: rgba(255,255,255,0.85);
}
.foot .contact b { color: white; font-weight: 600; }
.subfoot {
  background: var(--brand-green-dark);
  color: rgba(255,255,255,0.55);
  font-size: 8px;
  padding: 4px 36px;
  text-align: center;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
"""


# ---------- Helpers ----------


def _logo_img(variant: str = "green", alt: str = "ArborActive") -> str:
    filename = "logo-green.png" if variant == "green" else "logo-white.png"
    uri = _logo_data_uri(filename)
    css_class = "logo" if variant == "green" else "logo-w"
    return f'<img class="{css_class}" src="{uri}" alt="{escape(alt)}">'


def _icon(tier: Tier) -> str:
    char, bg, fg = _ICON_SPECS[tier]
    return (
        '<svg class="icon-svg" viewBox="0 0 18 18" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        f'<circle cx="9" cy="9" r="9" fill="{bg}"/>'
        f'<text x="9" y="13" text-anchor="middle" fill="{fg}" '
        'font-family="Helvetica, Arial, sans-serif" font-size="11" '
        f'font-weight="700">{escape(char)}</text>'
        "</svg>"
    )


def _marker_svg() -> str:
    """Vertical line + dot marker, dark on paper."""
    return (
        '<svg viewBox="0 0 10 14" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        f'<line x1="5" y1="3" x2="5" y2="11" stroke="{INK}" stroke-width="2" '
        'stroke-linecap="round"/>'
        f'<circle cx="5" cy="3" r="3" fill="{INK}" stroke="{PAPER}" stroke-width="1.2"/>'
        "</svg>"
    )


def _format_scale_value(v: float) -> str:
    """Compact scale label: integers as e.g. '1,800', floats short like '0.05'."""
    if v >= 1000:
        return f"{round(v):,}"
    if v >= 10:
        return f"{round(v)}"
    if v == int(v):
        return f"{int(v)}"
    # Trim trailing zeros for floats like 0.50 -> 0.5
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s


def _threshold_bar(spec: ThresholdSpec, tv: TieredValue) -> str:
    """Five equal-width zones, marker overlay, numeric scale below."""
    zone_ranges = zone_numeric_ranges(spec)
    zone_idx = tier_to_zone_index(spec, tv.tier)
    zmin, zmax = zone_ranges[zone_idx]
    zspan = zmax - zmin or 1.0
    within = max(0.0, min(1.0, (tv.raw - zmin) / zspan))
    mx_pct = round(zone_idx * 20 + within * 20, 2)

    # Six scale labels: dmin, b0..b3, dmax (in ascending order regardless of direction).
    dmin, dmax = spec.display_range
    if spec.direction == "normal":
        b = spec.breakpoints
    else:
        b = (spec.breakpoints[3], spec.breakpoints[2], spec.breakpoints[1], spec.breakpoints[0])
    scale_pts = (dmin, b[0], b[1], b[2], b[3], dmax)

    parts: list[str] = ['<div class="bar-wrap">']
    parts.append(
        '<svg class="bar-svg" viewBox="0 0 100 6" preserveAspectRatio="none" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    )
    for i, fill in enumerate(ZONE_FILLS):
        parts.append(f'<rect fill="{fill}" x="{i * 20}" y="0" width="20" height="6"/>')
    parts.append("</svg>")
    parts.append(f'<div class="bar-marker" style="left: {mx_pct}%;">{_marker_svg()}</div>')
    parts.append('<div class="bar-scale">')
    for v in scale_pts:
        parts.append(f"<span>{escape(_format_scale_value(v))}</span>")
    parts.append("</div></div>")
    return "".join(parts)


def _toxic_pill(tv: TieredValue, *, with_status: bool = False) -> str:
    """Status chip for toxic-metal value. Green OK / red ELEVATED.

    ``with_status`` is opt-in: single-sample rows show the status word in the
    right-side ``.tier`` column instead, and would otherwise duplicate it.
    Dual-sample rows have no right-side tier column, so they pass
    ``with_status=True`` to keep the in-pill word as the only indicator.
    """
    modifier = "ok" if tv.tier is Tier.GOOD else "elevated"
    if tv.formatted == "low" or not tv.unit:
        value_html = escape(tv.formatted)
    else:
        value_html = f'{escape(tv.formatted)} <span class="pill-unit">{escape(tv.unit)}</span>'
    status_html = ""
    if with_status:
        status_word = "OK" if tv.tier is Tier.GOOD else "ELEVATED"
        status_html = f"<span>{status_word}</span>"
    return (
        f'<span class="toxic-pill toxic-pill--{modifier}">'
        f'<span class="toxic-pill__value">{value_html}</span>'
        f"{status_html}"
        "</span>"
    )


# ---------- Header / Summary ----------


def _render_header(report: Report) -> str:
    return (
        '<header class="hdr">'
        f"{_logo_img('green')}"
        "<div></div>"
        '<div class="meta">'
        f"<div>Lab Report &nbsp;·&nbsp; <b>{escape(report.report_date)}</b></div>"
        "<div>Issued by ArborActive</div>"
        "</div>"
        "</header>"
    )


def _summary_lead(samples: tuple[ClassifiedSample, ...]) -> tuple[str, str, str]:
    """Compute headline, body, and dot color from the worst tiers across samples."""
    bad_labels: list[str] = []
    warn_labels: list[str] = []
    for cs in samples:
        for label, tv in cs.nutrients:
            if tv.tier in (Tier.VERY_LOW, Tier.VERY_HIGH):
                if label not in bad_labels:
                    bad_labels.append(label)
            elif tv.tier in (Tier.LOW, Tier.HIGH) and label not in warn_labels:
                warn_labels.append(label)

    if bad_labels:
        head = (
            f"{len(bad_labels)} priority gap" + ("s" if len(bad_labels) != 1 else "") + " detected"
        )
        body = (
            "Critical readings on "
            + ", ".join(bad_labels[:4])
            + (" and others." if len(bad_labels) > 4 else ".")
        )
        return head, body, "bad"
    if warn_labels:
        head = "Mostly healthy — minor adjustments"
        body = (
            "Watch "
            + ", ".join(warn_labels[:4])
            + (" and others." if len(warn_labels) > 4 else "; everything else within range.")
        )
        return head, body, "warn"
    return (
        "Healthy soil profile",
        "All tested values fall within standard agronomic ranges.",
        "good",
    )


def _render_title(report: Report) -> str:
    if report.title.lower().endswith("soil report"):
        # Stylize with italic on " Soil Report" portion.
        prefix = report.title[: -len("Soil Report")].strip()
        title_html = (
            f"{escape(prefix)} <em>Soil Report</em>"
            if prefix
            else f"<em>{escape(report.title)}</em>"
        )
    else:
        title_html = escape(report.title)
    sample_tags = "".join(
        f'<div class="sample-tag">Sample <b>{escape(cs.sample.name)}</b></div>'
        for cs in report.samples
    )
    return (
        '<div class="title-row">'
        "<div>"
        '<div class="eyebrow">Soil Nutrient Analysis</div>'
        f'<h1 class="title">{title_html}</h1>'
        '<p class="subtitle">A whole-soil picture scored against standard '
        "agronomic ranges. Center of each track is optimal; left and right "
        "bands flag values that need attention.</p>"
        "</div>"
        f'<div class="sample-tags">{sample_tags}</div>'
        "</div>"
    )


def _summary_quick_value(samples: tuple[ClassifiedSample, ...], label: str) -> str:
    """Pick the first sample's value for a label, formatted with unit."""
    cs = samples[0]
    for lbl, tv in cs.nutrients:
        if lbl == label:
            unit = f'<span class="unit">{escape(tv.unit)}</span>' if tv.unit else ""
            return f"{escape(tv.formatted)}{unit}"
    return "—"


def _render_summary(report: Report) -> str:
    head, body, dot_class = _summary_lead(report.samples)
    return (
        '<div class="summary">'
        '<div class="cell lead">'
        f'<div class="head"><span class="dot {dot_class}"></span>'
        f"<h3>{escape(head)}</h3></div>"
        f"<p>{escape(body)}</p>"
        "</div>"
        f'<div class="cell"><div class="lbl">pH</div>'
        f'<div class="val">{_summary_quick_value(report.samples, "pH")}</div></div>'
        f'<div class="cell"><div class="lbl">CEC</div>'
        f'<div class="val">{_summary_quick_value(report.samples, "CEC")}</div></div>'
        '<div class="cell"><div class="lbl">Organic Matter</div>'
        f'<div class="val">{_summary_quick_value(report.samples, "Organic Matter")}</div></div>'
        "</div>"
    )


# ---------- Sections ----------


# Sub-element shorthand for the row name (e.g. "K" for Potassium).
_SHORT: dict[str, str] = {
    "Calcium": "Ca",
    "Magnesium": "Mg",
    "Potassium": "K",
    "Phosphorus": "P",
    "Boron": "B",
    "Copper": "Cu",
    "Iron": "Fe",
    "Manganese": "Mn",
    "Zinc": "Zn",
    "Sulfur": "S",
    "Aluminum": "Al",
    "Lead (Pb)": "Pb",
    "pH": "acidity",
    "CEC": "meq/100g",
    "Organic Matter": "%",
}


def _render_name(label: str) -> str:
    sub = _SHORT.get(label, "")
    sub_html = f'<span class="sub">{escape(sub)}</span>' if sub else ""
    return f'<div class="name">{escape(label)}{sub_html}</div>'


def _tier_word(tier: Tier) -> str:
    word, _cls = _TIER_LABEL[tier]
    return word


def _tier_class(tier: Tier) -> str:
    _word, cls = _TIER_LABEL[tier]
    return cls


def _render_nutrient_row_single(spec: ThresholdSpec, tv: TieredValue) -> str:
    return (
        '<div class="row single">'
        f"{_icon(tv.tier)}"
        f"{_render_name(spec.label)}"
        f'<span class="val">{escape(tv.formatted)}</span>'
        f"{_threshold_bar(spec, tv)}"
        f'<span class="tier {_tier_class(tv.tier)}">{escape(_tier_word(tv.tier))}</span>'
        "</div>"
    )


def _worst_tier(a: Tier, b: Tier) -> Tier:
    """Return the more-severe tier; severity = distance from GOOD. Tie -> a."""
    pa = abs(a.value - Tier.GOOD.value)
    pb = abs(b.value - Tier.GOOD.value)
    return b if pb > pa else a


def _render_nutrient_row_dual(
    spec: ThresholdSpec,
    tvs: tuple[TieredValue, TieredValue],
) -> str:
    a, b = tvs
    worst = _worst_tier(a.tier, b.tier)
    a_cls = _tier_class(a.tier)
    b_cls = _tier_class(b.tier)
    return (
        '<div class="row dual">'
        f"{_icon(worst)}"
        f"{_render_name(spec.label)}"
        f'<span class="val col-a {a_cls}">{escape(a.formatted)}</span>'
        f"{_threshold_bar(spec, a)}"
        f'<span class="val col-b {b_cls}">{escape(b.formatted)}</span>'
        f"{_threshold_bar(spec, b)}"
        "</div>"
    )


def _render_toxic_row_single(spec: ToxicSpec, tv: TieredValue) -> str:
    # Pill carries its own value and status text; no scale/numeric column.
    return (
        '<div class="row single">'
        f"{_icon(tv.tier)}"
        f"{_render_name(spec.label)}"
        "<span></span>"
        f"<div>{_toxic_pill(tv)}</div>"
        f'<span class="tier {_tier_class(tv.tier)}">'
        f'{"OK" if tv.tier is Tier.GOOD else "Elevated"}</span>'
        "</div>"
    )


def _render_toxic_row_dual(spec: ToxicSpec, tvs: tuple[TieredValue, TieredValue]) -> str:
    a, b = tvs
    worst = _worst_tier(a.tier, b.tier)
    return (
        '<div class="row dual">'
        f"{_icon(worst)}"
        f"{_render_name(spec.label)}"
        "<span></span>"
        f"<div>{_toxic_pill(a, with_status=True)}</div>"
        "<span></span>"
        f"<div>{_toxic_pill(b, with_status=True)}</div>"
        "</div>"
    )


# Section groupings — labels match SPECS / TOXICS.
SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("01 · Foundation", ("pH", "CEC", "Organic Matter")),
    ("02 · Macronutrients", ("Calcium", "Magnesium", "Potassium", "Phosphorus")),
    ("03 · Micronutrients", ("Boron", "Copper", "Iron", "Manganese", "Zinc", "Sulfur")),
    ("04 · Contaminants", ("Aluminum", "Lead (Pb)")),
)


def _tv_for(cs: ClassifiedSample, label: str) -> TieredValue | None:
    for lbl, tv in cs.nutrients:
        if lbl == label:
            return tv
    return None


def _render_sections(samples: tuple[ClassifiedSample, ...]) -> str:
    parts: list[str] = []
    dual = len(samples) == 2
    if dual:
        a_name = escape(samples[0].sample.name)
        b_name = escape(samples[1].sample.name)
        # ONE shared column band rendered above the first section instead of a
        # repeating per-section row. Establishes column ownership once for the
        # whole data area and frees vertical space so the report still fits on
        # one US Letter page when two samples are compared.
        parts.append(
            '<div class="col-band">'
            "<span></span><span></span>"
            '<div class="col-name a">'
            f'<span>Sample</span><span class="nm">{a_name}</span>'
            "</div>"
            '<div class="col-name b">'
            f'<span>Sample</span><span class="nm">{b_name}</span>'
            "</div>"
            "</div>"
        )
    for head, labels in SECTIONS:
        parts.append('<section class="section">')
        parts.append('<div class="section-head">' f'<div class="h">{escape(head)}</div>' "</div>")
        for label in labels:
            toxic = toxic_lookup(label)
            if toxic is not None:
                if len(samples) == 1:
                    tv = _tv_for(samples[0], label)
                    if tv is not None:
                        parts.append(_render_toxic_row_single(toxic, tv))
                else:
                    a = _tv_for(samples[0], label)
                    b = _tv_for(samples[1], label)
                    if a is not None and b is not None:
                        parts.append(_render_toxic_row_dual(toxic, (a, b)))
            else:
                spec = SPEC_BY_LABEL.get(label)
                if spec is None:
                    continue
                if len(samples) == 1:
                    tv = _tv_for(samples[0], label)
                    if tv is not None:
                        parts.append(_render_nutrient_row_single(spec, tv))
                else:
                    a = _tv_for(samples[0], label)
                    b = _tv_for(samples[1], label)
                    if a is not None and b is not None:
                        parts.append(_render_nutrient_row_dual(spec, (a, b)))
        parts.append("</section>")
    return "".join(parts)


def _render_footer(report: Report) -> str:
    contact_bits: list[str] = []
    if report.contact_address:
        contact_bits.append(f"<b>{escape(report.contact_address)}</b>")
    line2_bits: list[str] = []
    if report.contact_email:
        line2_bits.append(f"<b>{escape(report.contact_email)}</b>")
    if report.contact_phone:
        line2_bits.append(f"<b>{escape(report.contact_phone)}</b>")
    contact_html = "<br>".join(
        x
        for x in [
            " · ".join(contact_bits) if contact_bits else "",
            " &nbsp;·&nbsp; ".join(line2_bits) if line2_bits else "",
        ]
        if x
    )
    return (
        '<div class="foot-block">'
        '<footer class="foot">'
        f"{_logo_img('white')}"
        f'<div class="contact">{contact_html}</div>'
        "</footer>"
        '<div class="subfoot">'
        f"Lab report generated {escape(report.report_date)} &nbsp;·&nbsp; "
        "Rooted in Science, Driven by Growth"
        "</div>"
        "</div>"
    )


def render(report: Report) -> str:
    """Render report to a single self-contained HTML string."""
    if len(report.samples) > 2:
        raise ValueError(
            f"render() supports at most 2 samples per report, got {len(report.samples)}"
        )
    parts = [
        "<!doctype html>\n",
        '<html lang="en">\n',
        "<head>\n",
        '<meta charset="utf-8">\n',
        f"<title>{escape(report.title)}</title>\n",
        "<style>",
        CSS,
        "</style>\n",
        "</head>\n",
        "<body>\n",
        f'<div class="page{" dual-mode" if len(report.samples) == 2 else ""}">',
        _render_header(report),
        _render_title(report),
        _render_summary(report),
        _render_sections(report.samples),
        _render_footer(report),
        "</div>\n",
        "</body>\n",
        "</html>\n",
    ]
    return "".join(parts)
