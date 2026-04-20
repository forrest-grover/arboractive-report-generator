"""Render twice from an in-memory synthetic Report, assert byte-identical."""

from __future__ import annotations

from pathlib import Path

from arboractive.classify import classify_all
from arboractive.models import Report, Sample
from arboractive.render import render


def _make_report() -> Report:
    samples = (
        Sample(
            name="site_a",
            lab_number="0001",
            received="1/1/2026",
            reported="1/15/2026",
            ph=5.2,
            calcium_lbs_acre=500,
            magnesium_lbs_acre=80,
            potassium_lbs_acre=100,
            phosphorus_lbs_acre=15,
            organic_matter_pct=4.2,
            cec_meq_100g=9.0,
        ),
        Sample(
            name="site_b",
            lab_number="0002",
            received="1/1/2026",
            reported="1/15/2026",
            ph=6.1,
            calcium_lbs_acre=2000,
            magnesium_lbs_acre=210,
            potassium_lbs_acre=320,
            phosphorus_lbs_acre=18,
            organic_matter_pct=5.5,
            cec_meq_100g=11.0,
        ),
    )
    classified = classify_all(samples)
    return Report(
        title="Demo Soil Report",
        site_name="Demo",
        report_date="January 2026",
        samples=classified,
        contact_name="",
        contact_address="",
        contact_email="",
        contact_phone="",
    )


def test_render_byte_identical() -> None:
    a = render(_make_report())
    b = render(_make_report())
    assert a == b, "two renders produced different HTML — non-determinism detected"
    assert len(a) > 2000
    assert "<!doctype html>" in a
    assert "Demo Soil Report" in a


def test_pdf_byte_identical(tmp_path: Path) -> None:
    from arboractive.cli import _write_pdf  # pylint: disable=import-outside-toplevel

    html = render(_make_report())
    out_a = tmp_path / "a.pdf"
    out_b = tmp_path / "b.pdf"
    _write_pdf(html, out_a)
    _write_pdf(html, out_b)
    assert out_a.read_bytes() == out_b.read_bytes(), "PDF output is non-deterministic"
    assert out_a.read_bytes().startswith(b"%PDF-")


def test_render_rejects_more_than_two_samples() -> None:
    import pytest  # pylint: disable=import-outside-toplevel

    sample = Sample(
        name="x",
        lab_number="1",
        received="1/1/2026",
        reported="1/1/2026",
        ph=6.5,
        calcium_lbs_acre=2000,
        magnesium_lbs_acre=200,
        potassium_lbs_acre=300,
        phosphorus_lbs_acre=17,
        organic_matter_pct=6.0,
        cec_meq_100g=12.0,
    )
    three = classify_all((sample, sample, sample))
    report = Report(
        title="x",
        site_name="x",
        report_date="x",
        samples=three,
        contact_name="",
        contact_address="",
        contact_email="",
        contact_phone="",
    )
    with pytest.raises(ValueError, match="at most 2 samples"):
        render(report)
