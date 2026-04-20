"""Classifier tier assertions using synthetic tier-boundary fixtures.

Each fixture sits cleanly inside one tier for every nutrient so that the
classifier's output is unambiguous. No real-world customer values.
"""

from __future__ import annotations

from arboractive.classify import classify
from arboractive.models import Sample, Tier

VERY_LOW_SAMPLE = Sample(
    name="very_low",
    lab_number="0000",
    received="1/1/2026",
    reported="1/1/2026",
    ph=4.0,
    calcium_lbs_acre=100,
    magnesium_lbs_acre=10,
    potassium_lbs_acre=10,
    phosphorus_lbs_acre=2,
    organic_matter_pct=0.5,
    cec_meq_100g=2.0,
)

GOOD_SAMPLE = Sample(
    name="good",
    lab_number="0001",
    received="1/1/2026",
    reported="1/1/2026",
    ph=6.5,
    calcium_lbs_acre=2100,
    magnesium_lbs_acre=200,
    potassium_lbs_acre=300,
    phosphorus_lbs_acre=17,
    organic_matter_pct=6.5,
    cec_meq_100g=12.0,
)

HIGH_SAMPLE = Sample(
    name="high",
    lab_number="0002",
    received="1/1/2026",
    reported="1/1/2026",
    ph=7.1,
    calcium_lbs_acre=3000,
    magnesium_lbs_acre=325,
    potassium_lbs_acre=425,
    phosphorus_lbs_acre=30,
    organic_matter_pct=9.0,
    cec_meq_100g=18.0,
)


def _tiers(sample: Sample) -> dict[str, Tier]:
    return {label: tv.tier for label, tv in classify(sample).nutrients}


def test_very_low_sample_classifies_all_very_low() -> None:
    assert set(_tiers(VERY_LOW_SAMPLE).values()) == {Tier.VERY_LOW}


def test_good_sample_classifies_all_good() -> None:
    assert set(_tiers(GOOD_SAMPLE).values()) == {Tier.GOOD}


def test_high_sample_classifies_all_high() -> None:
    assert set(_tiers(HIGH_SAMPLE).values()) == {Tier.HIGH}


def test_tier_boundary_inclusive_at_lower_good() -> None:
    """A value exactly at the lower bound of GOOD should register as GOOD."""
    # Calcium lower bound of GOOD is 1800
    s = Sample(
        name="edge",
        lab_number="0003",
        received="1/1/2026",
        reported="1/1/2026",
        ph=6.0,  # boundary LOW→GOOD
        calcium_lbs_acre=1800,  # boundary LOW→GOOD
        magnesium_lbs_acre=175,  # boundary LOW→GOOD
        potassium_lbs_acre=250,  # boundary LOW→GOOD
        phosphorus_lbs_acre=14,  # boundary LOW→GOOD
        organic_matter_pct=5.0,  # boundary LOW→GOOD
        cec_meq_100g=10.0,  # boundary LOW→GOOD
    )
    assert set(_tiers(s).values()) == {Tier.GOOD}
