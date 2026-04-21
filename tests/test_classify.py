"""Classifier tier assertions using synthetic tier-boundary fixtures."""

from __future__ import annotations

from arboractive.classify import classify
from arboractive.models import Sample, Tier

from ._fixtures import make_sample

VERY_LOW_SAMPLE = make_sample(
    ph=4.0,
    calcium_lbs_acre=100,
    magnesium_lbs_acre=10,
    potassium_lbs_acre=10,
    phosphorus_lbs_acre=2,
    organic_matter_pct=0.5,
    cec_meq_100g=2.0,
)

GOOD_SAMPLE = make_sample()  # defaults already land in GOOD

HIGH_SAMPLE = make_sample(
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
    boundary = make_sample(
        ph=6.0,
        calcium_lbs_acre=1800,
        magnesium_lbs_acre=175,
        potassium_lbs_acre=250,
        phosphorus_lbs_acre=14,
        organic_matter_pct=5.0,
        cec_meq_100g=10.0,
    )
    assert set(_tiers(boundary).values()) == {Tier.GOOD}
