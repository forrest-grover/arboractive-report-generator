"""Threshold specs driving both tier classification and bar rendering.

Sources:
- Ca/Mg/K/P (lbs/acre, Modified Morgan): UConn Soil Nutrient Analysis Lab
  https://soiltesting.cahnr.uconn.edu/soil-test-results-for-agronomic-crops/
  The Below-Optimum band is split at its midpoint into VERY_LOW and LOW.
  Excessive band (P only) → VERY_HIGH.
- pH: UConn general guidance (6.0-6.8 preferred). VERY_LOW cutoff set at 5.5
  so moderately-acidic CT soils register as critically low.
- CEC: UConn "typical 5-20 meq/100g, 10 adequate".
- Organic Matter %: calibrated so 4-5% registers as LOW.

Toxic metals (Al, Pb) use a separate ``ToxicSpec`` type because the 5-tier
"sweet-spot-in-the-middle" bar is semantically wrong for them — *lower is
always better*. They render via their own one-direction visuals (see
render.py) and are classified on a three-band GOOD / HIGH / VERY_HIGH scale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import Tier


@dataclass(frozen=True)
class ThresholdSpec:
    label: str
    attr: str
    unit: str  # "lbs/acre", "%", "meq/100g", ""
    breakpoints: tuple[float, float, float, float]
    display_range: tuple[float, float]
    direction: Literal["normal", "inverted"]
    fmt: Literal["int", "decimal"]


@dataclass(frozen=True)
class ToxicSpec:
    """One-direction toxic-metal spec: lower is always better.

    - ``cutoff``: value at or above this is VERY_HIGH ("elevated").
    - ``caution_fraction``: values in ``[cutoff*caution_fraction, cutoff)``
      classify as HIGH (caution); below that is GOOD.

    Both Al and Pb render as pill-style status chips (green OK / red
    ELEVATED). An earlier gradient-bar style was removed when users
    reported the bar + cutoff tick was harder to read at a glance than
    a plain pill.
    """

    label: str
    attr: str
    unit: str
    cutoff: float
    caution_fraction: float
    fmt: Literal["int", "decimal"]


SPECS: tuple[ThresholdSpec, ...] = (
    ThresholdSpec("pH", "ph", "", (5.5, 6.0, 6.8, 7.3), (4.0, 8.5), "normal", "decimal"),
    ThresholdSpec(
        "Calcium",
        "calcium_lbs_acre",
        "lbs/acre",
        (900, 1800, 2399, 3400),
        (0, 4500),
        "normal",
        "int",
    ),
    ThresholdSpec(
        "Magnesium",
        "magnesium_lbs_acre",
        "lbs/acre",
        (88, 175, 249, 400),
        (0, 500),
        "normal",
        "int",
    ),
    ThresholdSpec(
        "Potassium",
        "potassium_lbs_acre",
        "lbs/acre",
        (125, 250, 349, 500),
        (0, 700),
        "normal",
        "int",
    ),
    ThresholdSpec(
        "Phosphorus", "phosphorus_lbs_acre", "lbs/acre", (7, 14, 20, 40), (0, 60), "normal", "int"
    ),
    ThresholdSpec(
        "Organic Matter", "organic_matter_pct", "%", (2, 5, 8, 10), (0, 15), "normal", "decimal"
    ),
    ThresholdSpec("CEC", "cec_meq_100g", "meq/100g", (5, 10, 15, 20), (0, 30), "normal", "decimal"),
    ThresholdSpec(
        "Boron", "boron_ppm", "ppm", (0.05, 0.1, 2.0, 3.0), (0, 4.0), "normal", "decimal"
    ),
    ThresholdSpec(
        "Copper", "copper_ppm", "ppm", (0.15, 0.3, 0.8, 1.2), (0, 1.6), "normal", "decimal"
    ),
    ThresholdSpec(
        "Iron", "iron_ppm", "ppm", (0.5, 1.0, 40.0, 60.0), (0, 80.0), "normal", "decimal"
    ),
    ThresholdSpec(
        "Manganese",
        "manganese_ppm",
        "ppm",
        (1.5, 3.0, 20.0, 30.0),
        (0, 40.0),
        "normal",
        "decimal",
    ),
    ThresholdSpec(
        "Zinc", "zinc_ppm", "ppm", (0.05, 0.1, 70.0, 105.0), (0, 140.0), "normal", "decimal"
    ),
    ThresholdSpec("Sulfur", "sulfur_ppm", "ppm", (5, 10, 100, 150), (0, 200), "normal", "int"),
)


TOXICS: tuple[ToxicSpec, ...] = (
    ToxicSpec("Aluminum", "aluminum_ppm", "ppm", 300.0, 0.8, "int"),
    ToxicSpec("Lead (Pb)", "lead_ppm", "ppm", 100.0, 0.8, "int"),
)

# Tuple-of-pairs lookup instead of a dict so the determinism contract
# (no dicts/sets across boundaries) holds. Two entries — a linear scan is fine.
TOXIC_BY_LABEL: tuple[tuple[str, ToxicSpec], ...] = tuple((t.label, t) for t in TOXICS)


SPEC_BY_LABEL: dict[str, ThresholdSpec] = {s.label: s for s in SPECS}

# Tier → visual zone index (0 = leftmost). Precomputed per direction so callers
# don't rebuild the dict on every lookup. For `inverted` nutrients the mapping
# is the reverse (highest numeric values sit in the leftmost zone).
_TIER_ZONE_NORMAL: dict[Tier, int] = {
    Tier.VERY_LOW: 0,
    Tier.LOW: 1,
    Tier.GOOD: 2,
    Tier.HIGH: 3,
    Tier.VERY_HIGH: 4,
}
_TIER_ZONE_INVERTED: dict[Tier, int] = {
    Tier.VERY_HIGH: 0,
    Tier.HIGH: 1,
    Tier.GOOD: 2,
    Tier.LOW: 3,
    Tier.VERY_LOW: 4,
}


def tier_for(spec: ThresholdSpec, v: float) -> Tier:
    bp = spec.breakpoints
    if spec.direction == "normal":
        if v < bp[0]:
            return Tier.VERY_LOW
        if v < bp[1]:
            return Tier.LOW
        if v <= bp[2]:
            return Tier.GOOD
        if v <= bp[3]:
            return Tier.HIGH
        return Tier.VERY_HIGH
    if v >= bp[0]:
        return Tier.VERY_LOW
    if v >= bp[1]:
        return Tier.LOW
    if v >= bp[2]:
        return Tier.GOOD
    if v >= bp[3]:
        return Tier.HIGH
    return Tier.VERY_HIGH


def toxic_tier_for(spec: ToxicSpec, v: float) -> Tier:
    """Three-band classification for toxic metals.

    - ``v < cutoff * caution_fraction`` → GOOD
    - ``cutoff * caution_fraction <= v < cutoff`` → HIGH (caution)
    - ``v >= cutoff`` → VERY_HIGH (elevated)

    VERY_LOW / LOW are structurally unreachable — "lower" is always "better"
    on a toxic-metal axis, so there's no below-optimal band.
    """
    caution = spec.cutoff * spec.caution_fraction
    if v < caution:
        return Tier.GOOD
    if v < spec.cutoff:
        return Tier.HIGH
    return Tier.VERY_HIGH


def toxic_lookup(label: str) -> ToxicSpec | None:
    """Return the ToxicSpec for ``label`` or None. Linear scan by design."""
    for name, spec in TOXIC_BY_LABEL:
        if name == label:
            return spec
    return None


def _zone_boundaries_asc(spec: ThresholdSpec) -> tuple[float, float, float, float]:
    if spec.direction == "normal":
        return spec.breakpoints
    b = spec.breakpoints
    return (b[3], b[2], b[1], b[0])


def zone_numeric_ranges(spec: ThresholdSpec) -> tuple[tuple[float, float], ...]:
    dmin, dmax = spec.display_range
    asc = _zone_boundaries_asc(spec)
    return (
        (dmin, asc[0]),
        (asc[0], asc[1]),
        (asc[1], asc[2]),
        (asc[2], asc[3]),
        (asc[3], dmax),
    )


def tier_to_zone_index(spec: ThresholdSpec, tier: Tier) -> int:
    mapping = _TIER_ZONE_NORMAL if spec.direction == "normal" else _TIER_ZONE_INVERTED
    return mapping[tier]


def format_value(spec: ThresholdSpec, v: float) -> str:
    return f"{round(v)}" if spec.fmt == "int" else f"{v:.1f}"


def format_toxic_value(spec: ToxicSpec, v: float) -> str:
    return f"{round(v)}" if spec.fmt == "int" else f"{v:.1f}"
