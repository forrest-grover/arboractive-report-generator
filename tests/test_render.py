"""Render-behavior tests: single-sample layout and PDF content."""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from arboractive.pipeline import write_pdf
from arboractive.render import render

from ._fixtures import DEMO_SAMPLE_A, DEMO_SAMPLE_B, make_report


def test_single_sample_omits_column_headers() -> None:
    html = render(make_report((DEMO_SAMPLE_A,)))
    assert (
        'class="col-header' not in html
    ), "single-sample HTML should not emit the column-header row"
    assert 'class="row-label"' in html
    assert "site_a" not in html  # name not surfaced in the table
    assert "Demo Soil Report" in html  # … but stays in the document title


def test_two_samples_keeps_column_headers() -> None:
    html = render(make_report((DEMO_SAMPLE_A, DEMO_SAMPLE_B)))
    # One empty label header + one header per sample = 3 col-header divs
    assert html.count('class="col-header') == 3
    assert "site_a" in html
    assert "site_b" in html


def test_single_sample_has_one_data_cell_per_row() -> None:
    html = render(make_report((DEMO_SAMPLE_A,)))
    # 7 nutrient rows x 1 sample = 7 cells
    assert html.count('<div class="cell">') == 7


def test_pdf_single_sample(tmp_path: Path) -> None:
    html = render(make_report((DEMO_SAMPLE_A,)))
    out = tmp_path / "single.pdf"
    write_pdf(html, out)
    data = out.read_bytes()
    assert data.startswith(b"%PDF-")
    assert data.endswith(b"%%EOF\n") or data.endswith(b"%%EOF")
    assert len(data) > 10_000


def test_pdf_two_samples(tmp_path: Path) -> None:
    html = render(make_report((DEMO_SAMPLE_A, DEMO_SAMPLE_B)))
    out = tmp_path / "two.pdf"
    write_pdf(html, out)
    assert out.read_bytes().startswith(b"%PDF-")


def test_pdf_contains_rendered_text_content(tmp_path: Path) -> None:
    """PDF text is extractable — confirms weasyprint produced real text,
    not outline paths — and contains the data that should be shown."""
    html = render(make_report((DEMO_SAMPLE_A, DEMO_SAMPLE_B)))
    out = tmp_path / "content.pdf"
    write_pdf(html, out)

    with pdfplumber.open(out) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # Title, sample names, nutrient row labels, and raw values must be present.
    assert "Demo Soil Report" in text
    assert "site_a" in text
    assert "site_b" in text
    assert "Calcium" in text
    assert "Magnesium" in text
    assert "500" in text  # DEMO_SAMPLE_A Calcium
    assert "2000" in text  # DEMO_SAMPLE_B Calcium
