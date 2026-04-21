"""Render twice from an in-memory synthetic Report, assert byte-identical."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from arboractive.pipeline import write_pdf
from arboractive.render import render

from ._fixtures import DEMO_SAMPLE_A, DEMO_SAMPLE_B, make_report, make_sample


def test_render_byte_identical() -> None:
    report = make_report((DEMO_SAMPLE_A, DEMO_SAMPLE_B))
    a = render(report)
    b = render(report)
    assert a == b, "two renders produced different HTML — non-determinism detected"
    assert len(a) > 2000
    assert "<!doctype html>" in a
    assert "Demo Soil Report" in a


def test_pdf_byte_identical(tmp_path: Path) -> None:
    html = render(make_report((DEMO_SAMPLE_A, DEMO_SAMPLE_B)))
    out_a = tmp_path / "a.pdf"
    out_b = tmp_path / "b.pdf"
    write_pdf(html, out_a)
    write_pdf(html, out_b)
    assert out_a.read_bytes() == out_b.read_bytes(), "PDF output is non-deterministic"
    assert out_a.read_bytes().startswith(b"%PDF-")


def test_pdf_single_sample_byte_identical(tmp_path: Path) -> None:
    """Single-sample PDFs must also be reproducible."""
    full = make_report((DEMO_SAMPLE_A, DEMO_SAMPLE_B))
    single = replace(full, samples=(full.samples[0],))
    html = render(single)
    out_a = tmp_path / "single_a.pdf"
    out_b = tmp_path / "single_b.pdf"
    write_pdf(html, out_a)
    write_pdf(html, out_b)
    assert out_a.read_bytes() == out_b.read_bytes()


def test_render_rejects_more_than_two_samples() -> None:
    sample = make_sample(name="x")
    report = make_report((sample, sample, sample), title="x", site_name="x", report_date="x")
    with pytest.raises(ValueError, match="at most 2 samples"):
        render(report)
