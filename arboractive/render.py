"""Render a Report to a single self-contained HTML document.

Nutrient rows use the 5-zone "sweet spot in the middle" bar. Toxic-metal rows
(Al, Pb) render as compact status pills because *lower is always better* for
contaminants — a symmetric 5-zone bar is semantically wrong, and an earlier
gradient-bar experiment with a cutoff tick proved harder to read at a glance
than a plain chip. Pill content:

- ``Pb`` with ``lead_ppm is None`` (lab "low"/below-detection) → green
  ``"LOW OK"``.
- Numeric below cutoff (GOOD) → green ``"{N} ppm OK"``.
- Caution band (HIGH) or at/above cutoff (VERY_HIGH) → red
  ``"{N} ppm ELEVATED"``.

Layout is tuned to fit 15 data rows + a compact header on a single US Letter
page under weasyprint; see the CSS block below.
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
    tier_to_zone_index,
    toxic_lookup,
    zone_numeric_ranges,
)

_ASSETS = Path(__file__).parent / "assets"


@cache
def _logo_data_uri(name: str) -> str:
    data = (_ASSETS / name).read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


# Five zones always render red-amber-green-amber-red left-to-right on the
# numeric axis, regardless of nutrient direction (symmetric 3-color scale).
# Colors applied as SVG `fill` attributes so weasyprint renders them (its SVG
# engine doesn't apply external CSS class selectors to nested SVG elements).
ZONE_FILLS = ("#d36156", "#eeac58", "#9bbd7a", "#eeac58", "#d36156")
INK = "#2a2a2a"

# Icon glyph + (background color, text color) per tier. Rendered as SVG so
# weasyprint draws true circles (HTML `border-radius` on a span produced ovals
# under weasyprint's layout). Symmetric 3-color scheme: extremes (VERY_LOW /
# VERY_HIGH) are red, mids (LOW / HIGH) amber, GOOD green.
_ICON_RED = ("#b33a2f", "#ffffff")
_ICON_AMBER = ("#e89020", "#333333")
_ICON_GREEN = ("#7aa451", "#ffffff")
TIER_ICON: dict[Tier, tuple[str, tuple[str, str]]] = {
    Tier.VERY_LOW: ("!", _ICON_RED),
    Tier.LOW: ("•", _ICON_AMBER),
    Tier.GOOD: ("✓", _ICON_GREEN),
    Tier.HIGH: ("•", _ICON_AMBER),
    Tier.VERY_HIGH: ("!", _ICON_RED),
}


# Layout tuned for one-page US Letter output with 15 data rows. Row vertical
# padding, bar height, and header sizes were shrunk from the original
# comfortable spacing; the comparison section now fits inside a single page
# so the `break-inside: avoid` anti-crash hack (previously required because
# weasyprint's grid engine crashed when splitting) is redundant — removed.
CSS = """
@page {
  /* Zero margin so the paper background fills the full printed/PDF page.
     Without this, weasyprint renders a white frame around the content. */
  margin: 0;
  size: Letter;
}
:root {
  /* CSS custom properties are only used for HTML-level styling (backgrounds,
     borders, text). SVG fills/strokes are inlined in the markup because
     weasyprint's SVG engine ignores external CSS for nested SVG elements. */
  --brand-green: #2d4a2b;
  --brand-green-dark: #1e3320;
  --paper: #e3d9bf;
  --paper-dark: #d5c9a8;
  --ink: #2a2a2a;
  --muted: #6a6a6a;
  --rule: #b8ac8d;
  --toxic-ok-bg: #d6e2c3;
  --toxic-ok-fg: #3d5a28;
  --toxic-elevated-bg: #efc7c2;
  --toxic-elevated-fg: #7a2019;
}
* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: Arial, Helvetica, sans-serif;
  font-size: 14px;
  line-height: 1.2;
}
html, body { height: 100%; }

@media screen {
  body {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
  .page {
    flex: 1 0 auto;
    width: 100%;
    max-width: 820px;
    margin: 0 auto;
    background: var(--paper);
    padding: 14px 34px 80px 34px;
    box-sizing: border-box;
  }
  .footer-block {
    flex-shrink: 0;
  }
}

@media print {
  body { position: relative; }
  .page {
    max-width: 820px;
    margin: 0 auto;
    background: var(--paper);
    /* Footer is ~78px tall — reserve that much bottom padding so it doesn't
       overlap the last data row. */
    padding: 14px 34px 90px 34px;
  }
  .footer-block {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
  }
}
.brand-header {
  text-align: center;
  margin-bottom: 6px;
}
.brand-header .logo {
  display: block;
  margin: 0 auto;
  max-width: 388px;
  height: auto;
}
h1.report-title {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 20px;
  font-weight: 700;
  text-align: center;
  line-height: 1.2;
  margin: 4px 0 8px 0;
  padding-top: 8px;
  border-top: 1px solid var(--rule);
  color: var(--ink);
}
.header-spacer {
  display: block;
  height: 56px;
}
.comparison {
  display: grid;
  gap: 0;
  border-top: 1px solid var(--rule);
  padding-top: 22px;
}
.comparison .col-header {
  font-family: Georgia, serif;
  font-weight: 700;
  font-size: 14px;
  line-height: 1.2;
  text-align: center;
  padding: 3px 9px;
  border-bottom: 2px solid var(--rule);
}
.comparison .col-header.label-col { text-align: left; }
.comparison .row-label {
  padding: 3px 12px;
  font-weight: 600;
  border-bottom: 1px solid var(--rule);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  font-size: 14px;
  line-height: 1.2;
  overflow: hidden;
}
.comparison .row-label small {
  font-weight: 400;
  color: var(--muted);
  margin-left: 5px;
  font-size: 12px;
  white-space: nowrap;
}
.comparison .cell {
  display: grid;
  grid-template-columns: 44px 1fr 32px;
  align-items: center;
  gap: 7px;
  padding: 3px 12px;
  border-bottom: 1px solid var(--rule);
  border-left: 1px solid var(--rule);
  overflow: hidden;
}
.comparison .cell .value {
  font-weight: 700;
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-size: 14px;
  line-height: 1.2;
}
.bar-wrap {
  position: relative;
  width: 100%;
  height: 27px;
}
.bar-svg {
  position: absolute;
  top: 2px;
  left: 0;
  width: 100%;
  height: 23px;
  display: block;
}
/* Bar fills/strokes are applied as SVG presentation attributes (see
   _threshold_bar) because weasyprint's SVG renderer ignores class-based CSS
   inside SVG. The CSS above on .bar-svg/.bar-wrap still applies to layout
   (position, size) since those are HTML-level properties. */
.bar-marker {
  position: absolute;
  top: 0;
  width: 12px;
  height: 27px;
  transform: translateX(-50%);
  pointer-events: none;
}
.bar-marker-svg { display: block; width: 12px; height: 27px; }
.toxic-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 9px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.2;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.toxic-pill--ok {
  background: var(--toxic-ok-bg);
  color: var(--toxic-ok-fg);
}
.toxic-pill--elevated {
  background: var(--toxic-elevated-bg);
  color: var(--toxic-elevated-fg);
}
.toxic-pill__value {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}
/* Escape the pill's uppercase transform for the unit ("ppm") so the numeric
   unit renders lowercase while the status word (OK / ELEVATED) stays
   uppercase. Only applied to numeric pills; the "LOW OK" None-Pb case has
   no unit span. */
.pill-unit {
  text-transform: none;
}
/* Icon circles are drawn as inline SVG (see _icon) so they stay truly round
   under weasyprint, which stretches HTML spans with border-radius into ovals. */
.icon-svg {
  display: inline-block;
  width: 22px;
  height: 22px;
  vertical-align: middle;
}
.footer {
  background: var(--brand-green);
  color: var(--paper);
  padding: 10px 34px 8px 34px;
  text-align: center;
}
.footer .logo {
  display: block;
  margin: 0 auto 5px auto;
  max-width: 150px;
  height: auto;
}
.footer .contact {
  font-size: 10px;
  color: var(--paper-dark);
}
.sub-footer {
  background: var(--brand-green-dark);
  color: var(--paper-dark);
  font-size: 9px;
  padding: 4px 34px;
  text-align: center;
}
"""


def _logo_img(variant: str = "green", alt: str = "ArborActive") -> str:
    """Render the ArborActive logo as an inline base64 <img>.

    variant: 'green' (dark logo for light backgrounds) or 'white' (for dark).
    """
    filename = "logo-green.png" if variant == "green" else "logo-white.png"
    uri = _logo_data_uri(filename)
    return f'<img class="logo" src="{uri}" alt="{escape(alt)}">'


def _threshold_bar(spec: ThresholdSpec, tv: TieredValue) -> str:
    """Balanced bar: 5 equal-width zones (20% each) + a fixed-size marker
    overlay. Zones stretch to fill the cell width; the marker does not.

    Zones SVG: viewBox 100x14, `preserveAspectRatio="none"` (stretches). Zones
    touch directly — color contrast carries the boundaries, no divider line.
    Marker overlay: 10x22 pill-shaped stripe with rounded caps, positioned
    absolutely at the value percent and centered via translateX(-50%). Stays
    the same visual size regardless of how wide the cell becomes.
    """
    zone_ranges = zone_numeric_ranges(spec)
    zone_idx = tier_to_zone_index(spec, tv.tier)
    zmin, zmax = zone_ranges[zone_idx]
    zspan = zmax - zmin or 1.0
    within = max(0.0, min(1.0, (tv.raw - zmin) / zspan))
    mx_pct = round(zone_idx * 20 + within * 20, 2)

    parts: list[str] = [
        '<div class="bar-wrap">',
        '<svg class="bar-svg" viewBox="0 0 100 14" preserveAspectRatio="none" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">',
    ]
    for i, fill in enumerate(ZONE_FILLS):
        parts.append(f'<rect fill="{fill}" x="{i * 20}" y="0" width="20" height="14"/>')
    parts.append("</svg>")
    parts.append(
        f'<div class="bar-marker" style="left: {mx_pct}%;">'
        '<svg class="bar-marker-svg" viewBox="0 0 10 22" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<line x1="5" y1="2" x2="5" y2="20" stroke="#ffffff" stroke-width="5" '
        'stroke-linecap="round"/>'
        f'<line x1="5" y1="2" x2="5" y2="20" stroke="{INK}" stroke-width="2.5" '
        'stroke-linecap="round"/>'
        "</svg></div></div>"
    )
    return "".join(parts)


def _toxic_pill(tv: TieredValue) -> str:
    """Status chip for a toxic-metal value.

    Layout: ``{value-text} {STATUS}`` where:

    - GOOD (below caution) → green ``--ok`` modifier; status word ``OK``.
    - HIGH (caution band) or VERY_HIGH (at/above cutoff) → red ``--elevated``
      modifier; status word ``ELEVATED``. HIGH is surfaced as ELEVATED
      because a caution-band toxic still warrants action.

    ``tv.formatted`` is the pre-formatted numeric string (e.g., ``"187"``)
    or the literal ``"low"`` for the None-Pb case. For numeric values we
    append ``tv.unit`` (``"ppm"``) so the chip is self-describing; the
    literal ``"low"`` is already a complete word and stays unitless.
    CSS ``text-transform: uppercase`` on ``.toxic-pill`` renders the status
    word uppercase; the unit is wrapped in ``.pill-unit`` (``text-transform:
    none``) so ``ppm`` stays lowercase while ``OK``/``ELEVATED`` don't.
    """
    if tv.tier is Tier.GOOD:
        modifier = "ok"
        status = "OK"
    else:
        modifier = "elevated"
        status = "ELEVATED"
    if tv.formatted == "low" or not tv.unit:
        value_html = escape(tv.formatted)
    else:
        value_html = f'{escape(tv.formatted)} <span class="pill-unit">{escape(tv.unit)}</span>'
    return (
        f'<span class="toxic-pill toxic-pill--{modifier}">'
        f'<span class="toxic-pill__value">{value_html}</span>'
        f"<span>{status}</span>"
        "</span>"
    )


def _render_toxic_cell(tv: TieredValue) -> str:
    # Pill carries its own value text and status chip — no separate
    # numeric column or trailing icon, which would just be noise.
    return f'<div class="cell" style="grid-template-columns: 1fr;">{_toxic_pill(tv)}</div>'


def _icon(tier: Tier) -> str:
    char, (bg, fg) = TIER_ICON[tier]
    return (
        '<svg class="icon-svg" viewBox="0 0 22 22" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        f'<circle cx="11" cy="11" r="11" fill="{bg}"/>'
        f'<text x="11" y="15.5" text-anchor="middle" fill="{fg}" '
        'font-family="Arial, Helvetica, sans-serif" font-size="13" '
        f'font-weight="700">{escape(char)}</text>'
        "</svg>"
    )


def _render_row_label(label: str, unit: str) -> str:
    unit_hint = f" <small>({escape(unit)})</small>" if unit else ""
    return f'<div class="row-label">{escape(label)}{unit_hint}</div>'


def _render_nutrient_cell(spec: ThresholdSpec, tv: TieredValue) -> str:
    return (
        '<div class="cell">'
        f'<span class="value">{escape(tv.formatted)}</span>'
        f"{_threshold_bar(spec, tv)}"
        f"{_icon(tv.tier)}"
        "</div>"
    )


def _render_comparison(samples: tuple[ClassifiedSample, ...]) -> str:
    n = len(samples)
    col_template = f"189px repeat({n}, 1fr)"
    out = [f'<section class="comparison" style="grid-template-columns: {col_template};">']
    if n > 1:
        out.append('<div class="col-header label-col"></div>')
        for cs in samples:
            out.append(f'<div class="col-header">{escape(cs.sample.name)}</div>')
    # Data rows — nutrient order comes from the first sample (all samples
    # share the same order, enforced by classify()).
    labels = tuple(lbl for lbl, _ in samples[0].nutrients)
    for i, label in enumerate(labels):
        toxic_spec = toxic_lookup(label)
        if toxic_spec is not None:
            out.append(_render_row_label(label, toxic_spec.unit))
            for cs in samples:
                _, tv = cs.nutrients[i]
                out.append(_render_toxic_cell(tv))
        else:
            nut_spec = SPEC_BY_LABEL[label]
            out.append(_render_row_label(nut_spec.label, nut_spec.unit))
            for cs in samples:
                _, tv = cs.nutrients[i]
                out.append(_render_nutrient_cell(nut_spec, tv))
    out.append("</section>")
    return "".join(out)


def _render_header() -> str:
    return f'<header class="brand-header">{_logo_img(variant="green")}</header>'


def _render_footer(report: Report) -> str:
    return (
        '<div class="footer-block">'
        '<footer class="footer">'
        f"{_logo_img(variant='white')}"
        '<div class="contact">'
        f"{escape(report.contact_address)}"
        f"{'&nbsp;&middot;&nbsp;' if report.contact_email else ''}"
        f"{escape(report.contact_email)}"
        f"{'&nbsp;&middot;&nbsp;' if report.contact_phone else ''}"
        f"{escape(report.contact_phone)}"
        "</div>"
        "</footer>"
        f'<div class="sub-footer">Lab report generated {escape(report.report_date)}</div>'
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
        '<div class="page">\n',
        _render_header(),
        '<div class="header-spacer"></div>',
        f'<h1 class="report-title">{escape(report.title)}</h1>',
        _render_comparison(report.samples),
        "</div>\n",
        _render_footer(report),
        "</body>\n",
        "</html>\n",
    ]
    return "".join(parts)
