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
ZONE_CLASSES = ("zone-bad", "zone-warn", "zone-good", "zone-warn", "zone-bad")

# Icon char + css class — symmetric 3-color scheme:
# extremes (VERY_LOW/VERY_HIGH) are bad, mids (LOW/HIGH) are warn, GOOD is good.
TIER_ICON = {
    Tier.VERY_LOW: ("!", "icon-bad"),
    Tier.LOW: ("\u2022", "icon-warn"),
    Tier.GOOD: ("\u2713", "icon-good"),
    Tier.HIGH: ("\u2022", "icon-warn"),
    Tier.VERY_HIGH: ("!", "icon-bad"),
}


MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def _format_report_date(reported: str) -> str:
    """Convert '4/16/2026' to 'April 2026'. Pure string math, no datetime."""
    parts = reported.split("/")
    if len(parts) != 3:
        return reported
    month_str, _day, year = parts
    try:
        month_idx = int(month_str) - 1
        if 0 <= month_idx < 12:
            return f"{MONTHS[month_idx]} {year}"
    except ValueError:
        pass
    return reported


CSS = """
:root {
  /* Symmetric 3-color scale: extremes are bad (red), mids are caution (amber),
     GOOD is optimal (green). */
  /* Full-saturation accent colors — used for the tier indicator dots. */
  --tier-bad: #b33a2f;
  --tier-warn: #e89020;
  --tier-good: #7aa451;
  /* Bar zone fills — same hues at full saturation, lightened 25% toward
     white. Keeps the scale distinct from the paper background while staying
     quieter than the vivid indicator dots. */
  --zone-bad: #d36156;
  --zone-warn: #eeac58;
  --zone-good: #9bbd7a;
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
.page {
  max-width: 820px;
  margin: 0 auto;
  background: var(--paper);
  padding: 32px 40px 0 40px;
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
  margin-bottom: 28px;
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
.zone-bad { fill: var(--zone-bad); }
.zone-warn { fill: var(--zone-warn); }
.zone-good { fill: var(--zone-good); }
.zone-divider { stroke: rgba(42,42,42,0.25); stroke-width: 1; vector-effect: non-scaling-stroke; }
.bar-marker {
  position: absolute;
  top: 0;
  width: 14px;
  height: 46px;
  transform: translateX(-50%);
  pointer-events: none;
}
.bar-marker-svg { display: block; width: 14px; height: 46px; }
.bar-marker-line { stroke: var(--ink); stroke-width: 2.4; }
.bar-marker-line-outer { stroke: #fff; stroke-width: 5; }
.bar-marker-tri { fill: var(--ink); stroke: #fff; stroke-width: 1.2; stroke-linejoin: round; }
.icon {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 13px;
  font-family: Arial, sans-serif;
}
.icon.icon-bad { background: var(--tier-bad); }
.icon.icon-warn { background: var(--tier-warn); color: #333; }
.icon.icon-good { background: var(--tier-good); }
.footer {
  margin: 0 -40px;
  margin-top: 12px;
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
  margin: 0 -40px;
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

    Zones SVG: viewBox 100x26, `preserveAspectRatio="none"` (stretches).
    Marker overlay: 14x46 SVG, positioned absolutely at the value percent,
    centered on its x-coord via `transform: translateX(-50%)` so the marker
    keeps the same visual size regardless of how wide the cell becomes.
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
    for i, cls in enumerate(ZONE_CLASSES):
        parts.append(f'<rect class="{cls}" x="{i * 20}" y="0" width="20" height="26"/>')
    for i in range(1, 5):
        x = i * 20
        parts.append(f'<line class="zone-divider" x1="{x}" y1="0" x2="{x}" y2="26"/>')
    parts.append("</svg>")
    # Fixed-pixel-size marker overlay so the triangle/line stay crisp at any cell width.
    parts.append(
        f'<div class="bar-marker" style="left: {mx_pct}%;">'
        '<svg class="bar-marker-svg" viewBox="0 0 14 46" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<line class="bar-marker-line-outer" x1="7" y1="3" x2="7" y2="43"/>'
        '<line class="bar-marker-line" x1="7" y1="3" x2="7" y2="43"/>'
        '<polygon class="bar-marker-tri" points="2,0 12,0 7,10"/>'
        "</svg></div></div>"
    )
    return "".join(parts)


def _icon(tier: Tier) -> str:
    char, cls = TIER_ICON[tier]
    return f'<span class="icon {cls}">{escape(char)}</span>'


def _render_comparison(samples: tuple[ClassifiedSample, ...]) -> str:
    n = len(samples)
    col_template = f"180px repeat({n}, 1fr)"
    # Build header row
    out = [f'<section class="comparison" style="grid-template-columns: {col_template};">']
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
        '<div class="sub-footer">'
        f"Source&colon; Lab Report for &lsquo;{escape(report.site_name)}&rsquo; Samples, "
        f"{escape(report.report_date)}"
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
        _render_footer(report),
        "</div>\n",
        "</body>\n",
        "</html>\n",
    ]
    return "".join(parts)
