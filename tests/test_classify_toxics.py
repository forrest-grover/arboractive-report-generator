"""Toxic-metal classification covers the Al bar and Pb pill paths.

Both Al and Pb are classified via the generic ``TOXICS`` loop in
``classify.classify`` using ``thresholds.toxic_tier_for``. The three-band
semantics:

- ``v < cutoff * 0.8`` → GOOD
- ``cutoff * 0.8 <= v < cutoff`` → HIGH
- ``v >= cutoff`` → VERY_HIGH

Pb additionally supports ``None`` (the lab's "low" / below-detection reading)
which short-circuits to GOOD with ``formatted == "low"``.
"""

from __future__ import annotations

import pytest

from arboractive.classify import classify
from arboractive.models import Tier, TieredValue

from ._fixtures import make_sample

_AL_LABEL = "Aluminum"
_PB_LABEL = "Lead (Pb)"


def _tv(label: str, **overrides: object) -> TieredValue:
    return dict(classify(make_sample(**overrides)).nutrients)[label]


# --- Aluminum (pill, cutoff=300, caution=240) ---


@pytest.mark.parametrize(
    "raw,expected_tier,expected_formatted",
    [
        (0.0, Tier.GOOD, "0"),
        (155.0, Tier.GOOD, "155"),  # default fixture value — below caution
        (200.0, Tier.GOOD, "200"),  # below caution of 240
        (239.99, Tier.GOOD, "240"),  # just under caution
        (240.0, Tier.HIGH, "240"),  # exactly at caution
        (250.0, Tier.HIGH, "250"),  # within caution band
        (299.99, Tier.HIGH, "300"),  # just under cutoff
        (300.0, Tier.VERY_HIGH, "300"),  # exactly at cutoff → elevated
        (400.0, Tier.VERY_HIGH, "400"),  # well above cutoff
    ],
)
def test_aluminum_tier_bands(raw: float, expected_tier: Tier, expected_formatted: str) -> None:
    tv = _tv(_AL_LABEL, aluminum_ppm=raw)
    assert tv.tier is expected_tier
    assert tv.formatted == expected_formatted
    assert tv.unit == "ppm"


# --- Lead (pill, cutoff=100, caution=80) ---


def test_lead_none_is_good_low() -> None:
    tv = _tv(_PB_LABEL, lead_ppm=None)
    assert tv.tier is Tier.GOOD
    assert tv.formatted == "low"
    assert tv.unit == "ppm"
    assert tv.raw == 0.0


@pytest.mark.parametrize(
    "raw,expected_tier,expected_formatted",
    [
        (0.0, Tier.GOOD, "0"),
        (50.0, Tier.GOOD, "50"),  # below caution 80
        (79.99, Tier.GOOD, "80"),
        (80.0, Tier.HIGH, "80"),  # exactly at caution
        (99.99, Tier.HIGH, "100"),
        (100.0, Tier.VERY_HIGH, "100"),  # exactly at cutoff
        (186.7, Tier.VERY_HIGH, "187"),  # Booth-sample value
    ],
)
def test_lead_numeric_tiers(raw: float, expected_tier: Tier, expected_formatted: str) -> None:
    tv = _tv(_PB_LABEL, lead_ppm=raw)
    assert tv.tier is expected_tier
    assert tv.formatted == expected_formatted
    assert tv.unit == "ppm"
