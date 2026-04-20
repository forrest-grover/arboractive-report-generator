"""Parser tests against synthetic UConn-layout text.

Uses the internal `_parse_page` function so no real lab PDF is required.
"""

from __future__ import annotations

from arboractive.parse import _parse_page

SYNTHETIC_PAGE = """Soil Test Report Order Number: 99999
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
"""


def test_parse_synthetic_page() -> None:
    sample = _parse_page(SYNTHETIC_PAGE)
    assert sample is not None
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


def test_parse_skips_page_without_sample_header() -> None:
    assert _parse_page("Just some cover-sheet text\nNo sample info here.") is None
