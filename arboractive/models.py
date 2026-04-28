"""Frozen dataclasses that flow between modules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tier(Enum):
    VERY_LOW = 0
    LOW = 1
    GOOD = 2
    HIGH = 3
    VERY_HIGH = 4


@dataclass(frozen=True)
class Sample:
    name: str
    lab_number: str
    received: str
    reported: str
    ph: float
    calcium_lbs_acre: float
    magnesium_lbs_acre: float
    potassium_lbs_acre: float
    phosphorus_lbs_acre: float
    organic_matter_pct: float
    cec_meq_100g: float
    boron_ppm: float
    copper_ppm: float
    iron_ppm: float
    manganese_ppm: float
    zinc_ppm: float
    sulfur_ppm: float
    aluminum_ppm: float
    lead_ppm: float | None


@dataclass(frozen=True)
class TieredValue:
    raw: float
    formatted: str
    unit: str
    tier: Tier


@dataclass(frozen=True)
class ClassifiedSample:
    sample: Sample
    nutrients: tuple[tuple[str, TieredValue], ...]


@dataclass(frozen=True)
class Report:
    title: str
    site_name: str
    report_date: str
    samples: tuple[ClassifiedSample, ...]
    contact_address: str
    contact_email: str
    contact_phone: str
