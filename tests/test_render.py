"""Render-behavior tests: single-sample layout and PDF content."""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from arboractive.pipeline import write_pdf
from arboractive.render import render

from ._fixtures import DEMO_SAMPLE_A, DEMO_SAMPLE_B, make_report, make_sample


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
    # 7 macros + 6 micros + 2 toxics (Al pill, Pb pill) = 15 rows x 1 sample.
    # Pill cells have an inline grid override so match the class= prefix only.
    assert html.count('<div class="cell"') == 15


def test_toxic_pill_lead_none_renders_low_ok() -> None:
    # DEMO_SAMPLE_A has lead_ppm=None (inherited from fixture default) — pill
    # keeps the short "low OK" form; CSS uppercases it to "LOW OK" on render.
    html = render(make_report((DEMO_SAMPLE_A,)))
    assert (
        '<span class="toxic-pill toxic-pill--ok">'
        '<span class="toxic-pill__value">low</span><span>OK</span></span>'
    ) in html


def test_toxic_pill_lead_numeric_elevated_includes_ppm() -> None:
    # Pb above cutoff (Booth-sample value) must render as
    # "{N} ppm ELEVATED" in the red ("--elevated") chip. The unit is wrapped
    # in a `.pill-unit` span so CSS keeps "ppm" lowercase while the pill's
    # uppercase transform still applies to "ELEVATED".
    sample = make_sample(name="pb_hi", lead_ppm=186.7)
    html = render(make_report((sample,)))
    assert (
        '<span class="toxic-pill toxic-pill--elevated">'
        '<span class="toxic-pill__value">187 '
        '<span class="pill-unit">ppm</span></span><span>ELEVATED</span></span>'
    ) in html


def test_toxic_pill_aluminum_good_includes_ppm() -> None:
    # Al below caution band — green OK pill with lowercase ppm unit span.
    sample = make_sample(name="al_ok", aluminum_ppm=62.4)
    html = render(make_report((sample,)))
    assert (
        '<span class="toxic-pill toxic-pill--ok">'
        '<span class="toxic-pill__value">62 '
        '<span class="pill-unit">ppm</span></span><span>OK</span></span>'
    ) in html


def test_toxic_pill_aluminum_caution_renders_elevated() -> None:
    # Al in the caution band (240-299 ppm) has no dedicated pill style —
    # HIGH and VERY_HIGH both surface as the red ELEVATED chip so users
    # can't mistake a caution-band reading for "fine". Covers the
    # 80%-of-cutoff codepath that no source-PDF sample currently exercises.
    sample = make_sample(name="al_high", aluminum_ppm=260.0)
    html = render(make_report((sample,)))
    assert (
        '<span class="toxic-pill toxic-pill--elevated">'
        '<span class="toxic-pill__value">260 '
        '<span class="pill-unit">ppm</span></span><span>ELEVATED</span></span>'
    ) in html


def test_toxic_pill_aluminum_very_high_renders_elevated() -> None:
    sample = make_sample(name="al_vhi", aluminum_ppm=400.0)
    html = render(make_report((sample,)))
    assert (
        '<span class="toxic-pill toxic-pill--elevated">'
        '<span class="toxic-pill__value">400 '
        '<span class="pill-unit">ppm</span></span><span>ELEVATED</span></span>'
    ) in html


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
