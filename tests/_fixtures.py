"""Synthetic Sample/Report builders shared across test modules.

Kept as plain helpers (not pytest fixtures) so non-pytest test runners and
module-level constants can consume them the same way.
"""

from __future__ import annotations

from arboractive.classify import classify_all
from arboractive.models import Report, Sample

# Sensible defaults that land in every tier's GOOD zone so callers only need
# to override the field(s) relevant to their test.
_DEFAULT_FIELDS: dict[str, object] = {
    "name": "sample",
    "lab_number": "0000",
    "received": "1/1/2026",
    "reported": "1/1/2026",
    "ph": 6.5,
    "calcium_lbs_acre": 2000.0,
    "magnesium_lbs_acre": 200.0,
    "potassium_lbs_acre": 300.0,
    "phosphorus_lbs_acre": 17.0,
    "organic_matter_pct": 6.0,
    "cec_meq_100g": 12.0,
    "boron_ppm": 1.0,
    "copper_ppm": 0.5,
    "iron_ppm": 20.0,
    "manganese_ppm": 11.0,
    "zinc_ppm": 35.0,
    "sulfur_ppm": 55.0,
    "aluminum_ppm": 155.0,
    "lead_ppm": None,
}


def make_sample(**overrides: object) -> Sample:
    """Build a Sample with every tier at GOOD by default; override as needed."""
    return Sample(**{**_DEFAULT_FIELDS, **overrides})  # type: ignore[arg-type]


def make_report(samples: tuple[Sample, ...], **overrides: object) -> Report:
    """Build a Report around the given classified samples."""
    fields: dict[str, object] = {
        "title": "Demo Soil Report",
        "site_name": "Demo",
        "report_date": "January 2026",
        "samples": classify_all(samples),
        "contact_address": "",
        "contact_email": "",
        "contact_phone": "",
    }
    fields.update(overrides)
    return Report(**fields)  # type: ignore[arg-type]


# Two representative samples shared by multiple test modules. Site A sits in
# VERY_LOW/LOW tiers (acidic, nutrient-poor); site B straddles LOW/GOOD.
DEMO_SAMPLE_A = make_sample(
    name="site_a",
    lab_number="0001",
    ph=5.2,
    calcium_lbs_acre=500,
    magnesium_lbs_acre=80,
    potassium_lbs_acre=100,
    phosphorus_lbs_acre=15,
    organic_matter_pct=4.2,
    cec_meq_100g=9.0,
)

DEMO_SAMPLE_B = make_sample(
    name="site_b",
    lab_number="0002",
    ph=6.1,
    calcium_lbs_acre=2000,
    magnesium_lbs_acre=210,
    potassium_lbs_acre=320,
    phosphorus_lbs_acre=18,
    organic_matter_pct=5.5,
    cec_meq_100g=11.0,
)
