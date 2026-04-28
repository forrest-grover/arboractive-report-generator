"""Parser tests against synthetic UConn-layout text.

Uses the internal `_parse_page` function so no real lab PDF is required.
"""

from __future__ import annotations

from arboractive.models import Sample
from arboractive.parse import _parse_page

# Micros block (Boron through Aluminum) inserted between macros and Pb so the
# test fixture mirrors real UConn PDF layout. Pb is parameterized via
# _build_page so both "numeric" and "low" variants can be tested.
_HEADER = """Soil Test Report Order Number: 99999
Prepared For: Sample Information:
Test Person Sample Name: site_a
TestCo Lab Number: 0001
1 Nowhere Rd Area Sampled:
Nowhere, CT 00000 Received: 1/1/2026
Reported: 1/15/2026
Results
Nutrients Extracted From Your Soil (Modified Morgan)
Below Optimum Optimum Above Optimum Excessive*
Calcium 2000 lbs/acre
Magnesium 200 lbs/acre
Phosphorus 15 lbs/acre
Potassium 300 lbs/acre
Soil pH (1:1, H2O) 6.5
Est. Cation Exch. Capacity (meq/100g 12.0
% Organic Matter 6.0
Boron (B) 1.2 ppm
Copper (Cu) 0.55 ppm
Iron (Fe) 22.3 ppm
Manganese (Mn) 12.4 ppm
Zinc (Zn) 38.1 ppm
Sulfur (S) 45 ppm
Aluminum (Al) 160.5 ppm
"""


def _build_page(pb_line: str) -> str:
    return _HEADER + pb_line + "\n"


SYNTHETIC_PAGE = _build_page("Est. Total Lead (Pb) 42.7 ppm")
SYNTHETIC_PAGE_PB_LOW = _build_page("Est. Total Lead (Pb) low")


def _assert_shared_fields(sample: Sample) -> None:
    assert sample.name == "site_a"
    assert sample.lab_number == "0001"
    assert sample.received == "1/1/2026"
    assert sample.reported == "1/15/2026"
    assert sample.ph == 6.5
    assert sample.calcium_lbs_acre == 2000
    assert sample.magnesium_lbs_acre == 200
    assert sample.potassium_lbs_acre == 300
    assert sample.phosphorus_lbs_acre == 15
    assert sample.cec_meq_100g == 12.0
    assert sample.organic_matter_pct == 6.0
    assert sample.boron_ppm == 1.2
    assert sample.copper_ppm == 0.55
    assert sample.iron_ppm == 22.3
    assert sample.manganese_ppm == 12.4
    assert sample.zinc_ppm == 38.1
    assert sample.sulfur_ppm == 45
    assert sample.aluminum_ppm == 160.5


def test_parse_synthetic_page() -> None:
    sample = _parse_page(SYNTHETIC_PAGE)
    assert sample is not None
    _assert_shared_fields(sample)
    assert sample.lead_ppm == 42.7


def test_parse_synthetic_page_pb_low() -> None:
    sample = _parse_page(SYNTHETIC_PAGE_PB_LOW)
    assert sample is not None
    _assert_shared_fields(sample)
    assert sample.lead_ppm is None


def test_parse_skips_page_without_sample_header() -> None:
    assert _parse_page("Just some cover-sheet text\nNo sample info here.") is None
