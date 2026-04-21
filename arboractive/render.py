"""Render a Report to a single self-contained HTML document."""

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
    Tier.LOW: ("\u2022", _ICON_AMBER),
    Tier.GOOD: ("\u2713", _ICON_GREEN),
    Tier.HIGH: ("\u2022", _ICON_AMBER),
    Tier.VERY_HIGH: ("!", _ICON_RED),
}


CSS = """
@page {
  /* Zero margin so the paper background fills the full printed/PDF page.
     Without this, weasyprint renders a white frame around the content. */
  margin: 0;
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
}
* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: Arial, Helvetica, sans-serif;
  font-size: 14px;
  line-height: 1.4;
}
/* Sticky-footer: different techniques per medium so each renders correctly.
   - Screen (browsers): flex column. body fills viewport, .page flex-grows
     to push the footer-block to the bottom naturally. Footer stays below
     content without overlap regardless of window size.
   - Print (weasyprint): absolute positioning of footer-block at body bottom.
     weasyprint's flex support doesn't reliably honor `flex: 1` for a true
     sticky-footer, but absolute positioning with body = 100% works. */
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
    /* Extra bottom padding becomes visible gap between the table and the
       footer banner, since .page sits directly above the banner in flow. */
    padding: 32px 40px 120px 40px;
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
    padding: 32px 40px 200px 40px;
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
  padding-bottom: 18px;
  border-bottom: 1px solid var(--rule);
  margin-bottom: 24px;
}
.brand-header .logo {
  display: block;
  margin: 0 auto;
  max-width: 360px;
  height: auto;
}
h1.report-title {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 32px;
  font-weight: 700;
  text-align: center;
  margin: 16px 0 24px 0;
  color: var(--ink);
}
.comparison {
  display: grid;
  gap: 0;
  border-top: 1px solid var(--rule);
  margin-bottom: 32px;
}
.comparison .col-header {
  font-family: Georgia, serif;
  font-weight: 700;
  font-size: 15px;
  text-align: center;
  padding: 10px 8px;
  border-bottom: 2px solid var(--rule);
}
.comparison .col-header.label-col { text-align: left; }
.comparison .row-label {
  padding: 10px 12px;
  font-weight: 600;
  border-bottom: 1px solid var(--rule);
  display: flex;
  align-items: center;
}
.comparison .row-label small {
  font-weight: 400;
  color: var(--muted);
  margin-left: 6px;
  font-size: 11px;
}
.comparison .cell {
  display: grid;
  grid-template-columns: 48px 1fr 28px;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--rule);
  border-left: 1px solid var(--rule);
}
.comparison .cell .value {
  font-weight: 700;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.bar-wrap {
  position: relative;
  width: 100%;
  height: 46px;
}
.bar-svg {
  position: absolute;
  top: 10px;
  left: 0;
  width: 100%;
  height: 26px;
  display: block;
}
/* Bar fills/strokes are applied as SVG presentation attributes (see
   _threshold_bar) because weasyprint's SVG renderer ignores class-based CSS
   inside SVG. The CSS above on .bar-svg/.bar-wrap still applies to layout
   (position, size) since those are HTML-level properties. */
.bar-marker {
  position: absolute;
  top: 0;
  width: 14px;
  height: 46px;
  transform: translateX(-50%);
  pointer-events: none;
}
.bar-marker-svg { display: block; width: 14px; height: 46px; }
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
  padding: 22px 40px 18px 40px;
  text-align: center;
}
.footer .logo {
  display: block;
  margin: 0 auto 10px auto;
  max-width: 280px;
  height: auto;
}
.footer .contact {
  font-size: 12px;
  color: var(--paper-dark);
}
.sub-footer {
  background: var(--brand-green-dark);
  color: var(--paper-dark);
  font-size: 11px;
  padding: 8px 40px;
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

    Zones SVG: viewBox 100x26, `preserveAspectRatio="none"` (stretches). Zones
    touch directly — color contrast carries the boundaries, no divider line.
    Marker overlay: 14x46 pill-shaped stripe with rounded caps, positioned
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
        '<svg class="bar-svg" viewBox="0 0 100 26" preserveAspectRatio="none" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">',
    ]
    # Adjacent zones touch directly — alternating red/amber/green contrast
    # carries the boundaries; no divider needed.
    for i, fill in enumerate(ZONE_FILLS):
        parts.append(f'<rect fill="{fill}" x="{i * 20}" y="0" width="20" height="26"/>')
    parts.append("</svg>")
    # Fixed-pixel-size marker overlay: a pill-shaped vertical stripe.
    # Rounded caps + no triangle means no stray flat edges on the top or bottom.
    parts.append(
        f'<div class="bar-marker" style="left: {mx_pct}%;">'
        '<svg class="bar-marker-svg" viewBox="0 0 14 46" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<line x1="7" y1="4" x2="7" y2="42" stroke="#ffffff" stroke-width="6" '
        'stroke-linecap="round"/>'
        f'<line x1="7" y1="4" x2="7" y2="42" stroke="{INK}" stroke-width="3" '
        'stroke-linecap="round"/>'
        "</svg></div></div>"
    )
    return "".join(parts)


def _icon(tier: Tier) -> str:
    char, (bg, fg) = TIER_ICON[tier]
    # y=15 puts Arial-13 baselines roughly centered in a 22x22 circle for
    # "!", "•", and "✓". text-anchor="middle" handles horizontal centering.
    return (
        '<svg class="icon-svg" viewBox="0 0 22 22" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        f'<circle cx="11" cy="11" r="11" fill="{bg}"/>'
        f'<text x="11" y="15.5" text-anchor="middle" fill="{fg}" '
        'font-family="Arial, Helvetica, sans-serif" font-size="13" '
        f'font-weight="700">{escape(char)}</text>'
        "</svg>"
    )


def _render_comparison(samples: tuple[ClassifiedSample, ...]) -> str:
    n = len(samples)
    col_template = f"180px repeat({n}, 1fr)"
    out = [f'<section class="comparison" style="grid-template-columns: {col_template};">']
    # Column headers only when comparing — with a single sample the sample name is
    # already in the page title, so an extra header row is noise.
    if n > 1:
        out.append('<div class="col-header label-col"></div>')
        for cs in samples:
            out.append(f'<div class="col-header">{escape(cs.sample.name)}</div>')
    # Data rows — use nutrient order from first sample (all samples share order)
    labels = [lbl for lbl, _ in samples[0].nutrients]
    for i, label in enumerate(labels):
        spec = SPEC_BY_LABEL[label]
        unit_hint = f" <small>({escape(spec.unit)})</small>" if spec.unit else ""
        out.append(f'<div class="row-label">{escape(spec.label)}{unit_hint}</div>')
        for cs in samples:
            label_i, tv = cs.nutrients[i]
            spec = SPEC_BY_LABEL[label_i]
            out.append(
                '<div class="cell">'
                f'<span class="value">{escape(tv.formatted)}</span>'
                f"{_threshold_bar(spec, tv)}"
                f"{_icon(tv.tier)}"
                "</div>"
            )
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
        f'<h1 class="report-title">{escape(report.title)}</h1>',
        _render_comparison(report.samples),
        "</div>\n",
        _render_footer(report),
        "</body>\n",
        "</html>\n",
    ]
    return "".join(parts)
