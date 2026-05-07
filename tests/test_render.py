"""Render-behavior tests: single-sample layout and PDF content."""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from arboractive.pipeline import write_pdf
from arboractive.render import render

from ._fixtures import DEMO_SAMPLE_A, DEMO_SAMPLE_B, make_report, make_sample


def test_single_sample_omits_column_headers() -> None:
    html = render(make_report((DEMO_SAMPLE_A,)))
    # Layout discriminator: single-sample mode uses .row.single rows and
    # never the .row.dual two-column layout. This is the new design's
    # equivalent of "no per-sample column-header chrome inside sections".
    assert '<div class="row single"' in html
    assert '<div class="row dual"' not in html
    # Exactly one sample-tag chip lives in the title-row (header chrome),
    # not per-section, so the single sample isn't redundantly labelled.
    assert html.count('class="sample-tag"') == 1
    # Row labels still render.
    assert '<div class="name"' in html
    assert "Demo Soil Report" in html  # title preserved


def test_two_samples_keeps_column_headers() -> None:
    html = render(make_report((DEMO_SAMPLE_A, DEMO_SAMPLE_B)))
    # Two-sample mode flips to the dual-column row layout and surfaces a
    # sample-tag chip per sample so each value column is identified.
    assert '<div class="row dual"' in html
    assert '<div class="row single"' not in html
    assert html.count('class="sample-tag"') == 2
    assert "site_a" in html
    assert "site_b" in html


def test_single_sample_has_one_data_cell_per_row() -> None:
    html = render(make_report((DEMO_SAMPLE_A,)))
    # 3 foundation + 4 macros + 6 micros + 2 toxics = 15 rows x 1 sample.
    # Nutrient rows render a value as <span class="val">; toxic rows put
    # the value inside .toxic-pill__value instead. Together they count
    # one data cell per (row x sample): 15 in single-sample mode.
    nutrient_vals = html.count('<span class="val"')
    pill_vals = html.count('class="toxic-pill__value"')
    assert nutrient_vals + pill_vals == 15


def test_toxic_pill_lead_none_renders_low_ok() -> None:
    # DEMO_SAMPLE_A has lead_ppm=None (inherited from fixture default) — pill
    # carries only the value ("low"); status word ("OK") now rendered by the
    # row's right-side `.tier` column, not embedded in the pill.
    html = render(make_report((DEMO_SAMPLE_A,)))
    assert (
        '<span class="toxic-pill toxic-pill--ok">'
        '<span class="toxic-pill__value">low</span></span>'
    ) in html


def test_toxic_pill_lead_numeric_elevated_includes_ppm() -> None:
    # Pb above cutoff (Booth-sample value) renders the value alone in the red
    # ("--elevated") chip. The unit is wrapped in a `.pill-unit` span so CSS
    # keeps "ppm" lowercase against any surrounding uppercase transform.
    sample = make_sample(name="pb_hi", lead_ppm=186.7)
    html = render(make_report((sample,)))
    assert (
        '<span class="toxic-pill toxic-pill--elevated">'
        '<span class="toxic-pill__value">187 '
        '<span class="pill-unit">ppm</span></span></span>'
    ) in html


def test_toxic_pill_aluminum_good_includes_ppm() -> None:
    # Al below caution band — green OK pill with lowercase ppm unit span.
    sample = make_sample(name="al_ok", aluminum_ppm=62.4)
    html = render(make_report((sample,)))
    assert (
        '<span class="toxic-pill toxic-pill--ok">'
        '<span class="toxic-pill__value">62 '
        '<span class="pill-unit">ppm</span></span></span>'
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
        '<span class="pill-unit">ppm</span></span></span>'
    ) in html


def test_toxic_pill_aluminum_very_high_renders_elevated() -> None:
    sample = make_sample(name="al_vhi", aluminum_ppm=400.0)
    html = render(make_report((sample,)))
    assert (
        '<span class="toxic-pill toxic-pill--elevated">'
        '<span class="toxic-pill__value">400 '
        '<span class="pill-unit">ppm</span></span></span>'
    ) in html


def test_section_head_has_no_right_side_subtitle() -> None:
    # Sections render only the left "01 - Foundation" title; the faded
    # right-side subtitle (rendered via `.num`) was removed because the
    # column band + summary strip already convey unit/scale context.
    html = render(make_report((DEMO_SAMPLE_A,)))
    assert 'class="num"' not in html
    assert "pH · CEC · Organic Matter" not in html
    assert "lbs / acre" not in html
    # The left section title is still present.
    assert "01 · Foundation" in html


def test_single_toxic_row_pill_omits_in_pill_status() -> None:
    # Single-sample mode: in-pill status word is duplicated by the row's
    # right-side `.tier` column, so the pill drops it. The right-side
    # `.tier` span still renders the OK / Elevated word.
    html = render(make_report((DEMO_SAMPLE_A,)))
    # Pill itself has no <span>OK</span> / <span>ELEVATED</span> trailer.
    assert "<span>OK</span></span>" not in html
    assert "<span>ELEVATED</span></span>" not in html
    # Right-side `.tier` column still renders the status word.
    assert '<span class="tier good">OK</span>' in html


def test_dual_toxic_row_pill_keeps_in_pill_status() -> None:
    # Dual-sample mode has no right-side `.tier` column on toxic rows, so
    # the in-pill status word stays as the only indicator per sample.
    html = render(make_report((DEMO_SAMPLE_A, DEMO_SAMPLE_B)))
    assert "<span>OK</span></span>" in html


def test_dual_nutrient_values_carry_tier_classes() -> None:
    # Dual-sample nutrient values append the tier class so values render
    # in the tier color (good/warn/bad). Single-sample values stay plain.
    dual_html = render(make_report((DEMO_SAMPLE_A, DEMO_SAMPLE_B)))
    single_html = render(make_report((DEMO_SAMPLE_A,)))
    # DEMO_SAMPLE_A has VERY_LOW Calcium → "bad"; DEMO_SAMPLE_B is GOOD.
    assert 'class="val col-a bad"' in dual_html
    assert 'class="val col-b good"' in dual_html
    # Single-sample values have neither col-a/col-b nor a tier class.
    assert 'class="val col-a' not in single_html
    assert 'class="val good"' not in single_html
    assert 'class="val warn"' not in single_html
    assert 'class="val bad"' not in single_html


def test_dual_value_cells_have_no_color_accent() -> None:
    # The earlier `.col-a` / `.col-b` left-edge box-shadow accents (a dark
    # green bar on column A and an orange bar on column B, repeated on every
    # dual-sample row) were removed; tier color on the value text is the
    # only chromatic signal. Guard against regression.
    dual_html = render(make_report((DEMO_SAMPLE_A, DEMO_SAMPLE_B)))
    assert ".row.dual .val.col-a" not in dual_html
    assert ".row.dual .val.col-b" not in dual_html
    assert "box-shadow: inset 3px 0 0 var(--brand-green)" not in dual_html
    assert "box-shadow: inset 3px 0 0 var(--warn)" not in dual_html


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


def test_pdf_two_samples_paren_names(tmp_path: Path) -> None:
    """Regression: realistic UConn lab sample names like ``DaltonA(front)`` /
    ``DaltonB(back)`` (parser at parse.py:26 captures one non-space token,
    so the name + paren suffix arrive as one unbreakable token) used to
    crash weasyprint's grid layout at ``grid.py:1338`` with
    ``assert isinstance(new_child, boxes.ParentBox)``. Real cause:
    page-fragmentation of a ``.row.dual`` grid — when a grid cell's
    child is split across pages and the resulting box is a leaf inline
    (not a ``ParentBox``), weasyprint asserts. Long real-shape names
    push enough title-row height down that a row falls across the page
    boundary; ``break-inside: avoid`` on ``.row`` and ``.row.dual-head``
    keeps each row atomic so fragmentation never picks one. Plain
    short-token names (e.g. ``daltona``) don't shift content far
    enough to trigger the page break, so they don't reproduce."""
    sample_a = make_sample(name="DaltonA(front)", lab_number="0001")
    sample_b = make_sample(name="DaltonB(back)", lab_number="0002")
    html = render(make_report((sample_a, sample_b)))
    out = tmp_path / "paren_names.pdf"
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
    # Sample tags use CSS `text-transform: uppercase`, so pdfplumber extracts
    # the visually-rendered uppercase form rather than the source-case name.
    assert "Demo Soil Report" in text
    assert "SITE_A" in text
    assert "SITE_B" in text
    assert "Calcium" in text
    assert "Magnesium" in text
    assert "500" in text  # DEMO_SAMPLE_A Calcium
    assert "2000" in text  # DEMO_SAMPLE_B Calcium
