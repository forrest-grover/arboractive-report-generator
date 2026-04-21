"""Threshold tests for the inverted direction (no production spec uses it yet).

Exercises ``tier_for`` and ``_zone_boundaries_asc`` on an inverted spec so the
inverted branch stays live and regression-proof.
"""

from __future__ import annotations

from arboractive.models import Tier
from arboractive.thresholds import (
    ThresholdSpec,
    _zone_boundaries_asc,
    tier_for,
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
