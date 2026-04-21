"""Pipeline tests: build_report soft-degrade on contact parse failure.

The contact-block parser is soft-degraded — a malformed block shouldn't break
the whole report. We verify the result still carries a complete Report but
also flags the failure so callers (CLI/GUI) can surface a warning.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arboractive import pipeline
from arboractive.pipeline import BuildReportResult, build_report

from ._fixtures import DEMO_SAMPLE_A


def test_build_report_no_pdf_has_no_contact_failure() -> None:
    result = build_report((DEMO_SAMPLE_A,), pdf_path=None, title_override=None)
    assert isinstance(result, BuildReportResult)
    assert result.contact_parse_failed is False
    assert result.contact_error is None
    assert result.report.contact_address == ""
    assert result.report.contact_email == ""
    assert result.report.contact_phone == ""


def test_build_report_contact_parse_failure_is_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A raising find_contact is soft-degraded: Report still built, flag set."""

    def boom(_path: str | Path) -> tuple[str, str, str, str]:
        raise ValueError("malformed contact block")

    monkeypatch.setattr(pipeline, "find_contact", boom)

    result = build_report(
        (DEMO_SAMPLE_A,),
        pdf_path=Path("/does/not/matter.pdf"),
        title_override=None,
    )
    assert result.contact_parse_failed is True
    assert result.contact_error == "malformed contact block"
    # Report still rendered with empty contact fields — no exit-code-4 regression.
    assert result.report.contact_address == ""
    assert result.report.contact_email == ""
    assert result.report.contact_phone == ""
    assert result.report.samples  # samples still classified


def test_build_report_contact_success_clears_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def ok(_path: str | Path) -> tuple[str, str, str, str]:
        return ("Jane Doe", "1 Nowhere Rd, Nowhere, CT 00000", "j@x.test", "800-555-0100")

    monkeypatch.setattr(pipeline, "find_contact", ok)

    result = build_report(
        (DEMO_SAMPLE_A,),
        pdf_path=Path("/does/not/matter.pdf"),
        title_override=None,
    )
    assert result.contact_parse_failed is False
    assert result.contact_error is None
    assert result.report.contact_address == "1 Nowhere Rd, Nowhere, CT 00000"
    assert result.report.contact_email == "j@x.test"
    assert result.report.contact_phone == "800-555-0100"
