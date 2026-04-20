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
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Tier


@dataclass(frozen=True)
class ThresholdSpec:
    label: str
    attr: str
    unit: str  # "lbs/acre", "%", "meq/100g", ""
    breakpoints: tuple[float, float, float, float]
    display_range: tuple[float, float]
    direction: str  # "normal" | "inverted"
    fmt: str  # "int" | "decimal"


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
)

SPEC_BY_LABEL: dict[str, ThresholdSpec] = {s.label: s for s in SPECS}


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


def zone_boundaries_asc(spec: ThresholdSpec) -> tuple[float, float, float, float]:
    if spec.direction == "normal":
        return spec.breakpoints
    b = spec.breakpoints
    return (b[3], b[2], b[1], b[0])


def zone_numeric_ranges(spec: ThresholdSpec) -> tuple[tuple[float, float], ...]:
    dmin, dmax = spec.display_range
    asc = zone_boundaries_asc(spec)
    return (
        (dmin, asc[0]),
        (asc[0], asc[1]),
        (asc[1], asc[2]),
        (asc[2], asc[3]),
        (asc[3], dmax),
    )


def tier_to_zone_index(spec: ThresholdSpec, tier: Tier) -> int:
    if spec.direction == "normal":
        return {
            Tier.VERY_LOW: 0,
            Tier.LOW: 1,
            Tier.GOOD: 2,
            Tier.HIGH: 3,
            Tier.VERY_HIGH: 4,
        }[tier]
    return {
        Tier.VERY_HIGH: 0,
        Tier.HIGH: 1,
        Tier.GOOD: 2,
        Tier.LOW: 3,
        Tier.VERY_LOW: 4,
    }[tier]


def format_value(spec: ThresholdSpec, v: float) -> str:
    return f"{round(v)}" if spec.fmt == "int" else f"{v:.1f}"
