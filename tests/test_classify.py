"""Classifier tier assertions using synthetic tier-boundary fixtures.

Toxic metals (Al, Pb) don't fit the 5-tier nutrient scale — they classify on
a three-band GOOD / HIGH / VERY_HIGH axis (see ``test_classify_toxics.py``).
The assertions below exclude them when asserting on "all nutrients".
"""

from __future__ import annotations

from arboractive.classify import classify
from arboractive.models import Sample, Tier

from ._fixtures import make_sample

_TOXIC_LABELS = frozenset({"Aluminum", "Lead (Pb)"})

VERY_LOW_SAMPLE = make_sample(
    ph=4.0,
    calcium_lbs_acre=100,
    magnesium_lbs_acre=10,
    potassium_lbs_acre=10,
    phosphorus_lbs_acre=2,
    organic_matter_pct=0.5,
    cec_meq_100g=2.0,
    boron_ppm=0.0,
    copper_ppm=0.0,
    iron_ppm=0.0,
    manganese_ppm=0.0,
    zinc_ppm=0.0,
    sulfur_ppm=0.0,
    aluminum_ppm=0.0,
    lead_ppm=None,
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
    boron_ppm=2.5,
    copper_ppm=1.0,
    iron_ppm=50.0,
    manganese_ppm=25.0,
    zinc_ppm=85.0,
    sulfur_ppm=125.0,
    aluminum_ppm=375.0,
    lead_ppm=None,
)


def _tiers(sample: Sample) -> dict[str, Tier]:
    return {label: tv.tier for label, tv in classify(sample).nutrients}


def _tiers_nutrients_only(sample: Sample) -> dict[str, Tier]:
    return {label: tier for label, tier in _tiers(sample).items() if label not in _TOXIC_LABELS}


def test_very_low_sample_classifies_all_very_low() -> None:
    assert set(_tiers_nutrients_only(VERY_LOW_SAMPLE).values()) == {Tier.VERY_LOW}
    # Toxic-metal axis is one-directional: Al=0 and Pb=None both mean "clean"
    # and map to GOOD. VERY_LOW doesn't exist on the toxic axis.
    tiers = _tiers(VERY_LOW_SAMPLE)
    assert tiers["Aluminum"] is Tier.GOOD
    assert tiers["Lead (Pb)"] is Tier.GOOD


def test_good_sample_classifies_all_good() -> None:
    assert set(_tiers(GOOD_SAMPLE).values()) == {Tier.GOOD}


def test_high_sample_classifies_all_high() -> None:
    assert set(_tiers_nutrients_only(HIGH_SAMPLE).values()) == {Tier.HIGH}
    tiers = _tiers(HIGH_SAMPLE)
    # Al=375 >= cutoff 300 → VERY_HIGH on the toxic axis.
    assert tiers["Aluminum"] is Tier.VERY_HIGH
    # Pb=None → GOOD by the "low"-reading convention.
    assert tiers["Lead (Pb)"] is Tier.GOOD


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
        boron_ppm=0.1,
        copper_ppm=0.3,
        iron_ppm=1.0,
        manganese_ppm=3.0,
        zinc_ppm=0.1,
        sulfur_ppm=10.0,
        aluminum_ppm=10.0,
        lead_ppm=None,
    )
    assert set(_tiers(boundary).values()) == {Tier.GOOD}
