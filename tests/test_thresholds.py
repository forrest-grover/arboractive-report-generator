"""Threshold tests for the inverted direction (no production spec uses it yet).

Exercises ``tier_for`` and ``_zone_boundaries_asc`` on an inverted spec so the
inverted branch stays live and regression-proof. Also covers the micronutrient
boundaries and the toxic-metal (Al, Pb) three-band classification.
"""

from __future__ import annotations

from arboractive.models import Tier
from arboractive.thresholds import (
    SPEC_BY_LABEL,
    TOXIC_BY_LABEL,
    TOXICS,
    ThresholdSpec,
    ToxicSpec,
    _zone_boundaries_asc,
    tier_for,
    toxic_lookup,
    toxic_tier_for,
    zone_numeric_ranges,
)

# Inverted: higher numeric values are WORSE. Breakpoints descend so that
# tier_for's inverted branch (which compares with >=) yields the expected tiers.
_INVERTED = ThresholdSpec(
    label="Synthetic",
    attr="ph",
    unit="",
    breakpoints=(40.0, 30.0, 20.0, 10.0),
    display_range=(0.0, 50.0),
    direction="inverted",
    fmt="decimal",
)


def test_inverted_tier_for_each_band() -> None:
    # 45 >= 40 → VERY_LOW (the "worst" tier on an inverted axis)
    assert tier_for(_INVERTED, 45.0) is Tier.VERY_LOW
    # 35 >= 30 but < 40 → LOW
    assert tier_for(_INVERTED, 35.0) is Tier.LOW
    # 25 >= 20 but < 30 → GOOD
    assert tier_for(_INVERTED, 25.0) is Tier.GOOD
    # 15 >= 10 but < 20 → HIGH
    assert tier_for(_INVERTED, 15.0) is Tier.HIGH
    # 5 < 10 → VERY_HIGH (the "best" numerically-low tier on an inverted axis)
    assert tier_for(_INVERTED, 5.0) is Tier.VERY_HIGH


def test_inverted_zone_boundaries_asc_reverses_breakpoints() -> None:
    # Inverted: the ascending boundaries are the breakpoints reversed so the
    # left-to-right visual order still runs low → high numerically.
    assert _zone_boundaries_asc(_INVERTED) == (10.0, 20.0, 30.0, 40.0)


def test_inverted_zone_numeric_ranges_are_contiguous_and_ascending() -> None:
    ranges = zone_numeric_ranges(_INVERTED)
    assert ranges == (
        (0.0, 10.0),
        (10.0, 20.0),
        (20.0, 30.0),
        (30.0, 40.0),
        (40.0, 50.0),
    )


# Micronutrient specs — boundary-crossing samples per (label, breakpoints).
# Each row picks a representative value inside every tier so regressions in
# breakpoint tuples are caught immediately.
_BORON = SPEC_BY_LABEL["Boron"]
_COPPER = SPEC_BY_LABEL["Copper"]
_IRON = SPEC_BY_LABEL["Iron"]
_MANGANESE = SPEC_BY_LABEL["Manganese"]
_ZINC = SPEC_BY_LABEL["Zinc"]
_SULFUR = SPEC_BY_LABEL["Sulfur"]


def test_boron_tiers_span_bands() -> None:
    assert tier_for(_BORON, 0.01) is Tier.VERY_LOW
    assert tier_for(_BORON, 0.08) is Tier.LOW
    assert tier_for(_BORON, 1.0) is Tier.GOOD
    assert tier_for(_BORON, 2.5) is Tier.HIGH
    assert tier_for(_BORON, 3.5) is Tier.VERY_HIGH


def test_copper_tiers_span_bands() -> None:
    assert tier_for(_COPPER, 0.1) is Tier.VERY_LOW
    assert tier_for(_COPPER, 0.2) is Tier.LOW
    assert tier_for(_COPPER, 0.5) is Tier.GOOD
    assert tier_for(_COPPER, 1.0) is Tier.HIGH
    assert tier_for(_COPPER, 1.5) is Tier.VERY_HIGH


def test_iron_tiers_span_bands() -> None:
    assert tier_for(_IRON, 0.3) is Tier.VERY_LOW
    assert tier_for(_IRON, 0.75) is Tier.LOW
    assert tier_for(_IRON, 20.0) is Tier.GOOD
    assert tier_for(_IRON, 50.0) is Tier.HIGH
    assert tier_for(_IRON, 70.0) is Tier.VERY_HIGH


def test_manganese_tiers_span_bands() -> None:
    assert tier_for(_MANGANESE, 1.0) is Tier.VERY_LOW
    assert tier_for(_MANGANESE, 2.0) is Tier.LOW
    assert tier_for(_MANGANESE, 10.0) is Tier.GOOD
    assert tier_for(_MANGANESE, 25.0) is Tier.HIGH
    assert tier_for(_MANGANESE, 35.0) is Tier.VERY_HIGH


def test_zinc_tiers_span_bands() -> None:
    assert tier_for(_ZINC, 0.01) is Tier.VERY_LOW
    assert tier_for(_ZINC, 0.08) is Tier.LOW
    assert tier_for(_ZINC, 35.0) is Tier.GOOD
    assert tier_for(_ZINC, 85.0) is Tier.HIGH
    assert tier_for(_ZINC, 120.0) is Tier.VERY_HIGH


def test_sulfur_tiers_span_bands() -> None:
    assert tier_for(_SULFUR, 2.0) is Tier.VERY_LOW
    assert tier_for(_SULFUR, 7.0) is Tier.LOW
    assert tier_for(_SULFUR, 55.0) is Tier.GOOD
    assert tier_for(_SULFUR, 125.0) is Tier.HIGH
    assert tier_for(_SULFUR, 175.0) is Tier.VERY_HIGH


# --- Toxic metals: Al and Pb share three-band classification and both render
# as pills. Kept in TOXICS tuple so render dispatches via toxic_lookup. ---


def _toxic(label: str) -> ToxicSpec:
    spec = toxic_lookup(label)
    assert spec is not None, f"toxic spec {label!r} not registered"
    return spec


def test_toxics_registered_in_lookup() -> None:
    labels = tuple(label for label, _ in TOXIC_BY_LABEL)
    assert labels == ("Aluminum", "Lead (Pb)")
    assert len(TOXICS) == 2
    assert toxic_lookup("does-not-exist") is None
    # Toxic labels intentionally don't appear in the nutrient SPEC_BY_LABEL:
    # render.py dispatches toxics via toxic_lookup so a collision would be a bug.
    assert "Aluminum" not in SPEC_BY_LABEL
    assert "Lead (Pb)" not in SPEC_BY_LABEL


def test_aluminum_toxic_spec_values() -> None:
    al = _toxic("Aluminum")
    assert al.cutoff == 300.0
    assert al.caution_fraction == 0.8
    assert al.unit == "ppm"
    assert al.fmt == "int"


def test_lead_toxic_spec_values() -> None:
    pb = _toxic("Lead (Pb)")
    assert pb.cutoff == 100.0
    assert pb.caution_fraction == 0.8
    assert pb.unit == "ppm"
    assert pb.fmt == "int"


def test_aluminum_tier_bands() -> None:
    al = _toxic("Aluminum")
    # caution = 0.8 * 300 = 240
    assert toxic_tier_for(al, 0.0) is Tier.GOOD
    assert toxic_tier_for(al, 155.0) is Tier.GOOD
    assert toxic_tier_for(al, 239.99) is Tier.GOOD
    assert toxic_tier_for(al, 240.0) is Tier.HIGH  # exactly at caution boundary
    assert toxic_tier_for(al, 299.99) is Tier.HIGH
    assert toxic_tier_for(al, 300.0) is Tier.VERY_HIGH  # exactly at cutoff
    assert toxic_tier_for(al, 400.0) is Tier.VERY_HIGH


def test_lead_tier_bands() -> None:
    pb = _toxic("Lead (Pb)")
    # caution = 0.8 * 100 = 80
    assert toxic_tier_for(pb, 0.0) is Tier.GOOD
    assert toxic_tier_for(pb, 79.99) is Tier.GOOD
    assert toxic_tier_for(pb, 80.0) is Tier.HIGH
    assert toxic_tier_for(pb, 99.99) is Tier.HIGH
    assert toxic_tier_for(pb, 100.0) is Tier.VERY_HIGH
    assert toxic_tier_for(pb, 186.7) is Tier.VERY_HIGH
