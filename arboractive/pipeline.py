"""Shared pipeline: title derivation, report date formatting, PDF writing, report build.

Lives outside cli/gui so both entry points depend on this module without creating
a cycle between them. Pure string/date math and IO helpers — no rendering logic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import takewhile
from pathlib import Path

from .classify import classify_all
from .models import Report, Sample
from .parse import find_contact


@dataclass(frozen=True)
class BuildReportResult:
    """Outcome of build_report: the rendered Report plus contact-parse status.

    When the contact block in the source PDF can't be parsed, build_report
    still returns a complete Report (with empty contact fields) and sets
    ``contact_parse_failed`` so callers can surface a warning without having
    to re-invoke the parser.
    """

    report: Report
    contact_parse_failed: bool
    contact_error: str | None


# Fixed value for weasyprint's PDF CreationDate metadata. Any constant works;
# the point is that repeated runs with the same input produce byte-identical
# PDFs. weasyprint (and most reproducible-build tooling) honors this env var.
_DETERMINISTIC_SOURCE_DATE_EPOCH = "0"

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def write_pdf(html: str, out_path: Path) -> None:
    """Render HTML to a deterministic PDF at out_path."""
    os.environ["SOURCE_DATE_EPOCH"] = _DETERMINISTIC_SOURCE_DATE_EPOCH
    # Lazy import so pure-HTML workflows don't pay weasyprint startup cost.
    from weasyprint import HTML  # pylint: disable=import-outside-toplevel

    HTML(string=html).write_pdf(target=str(out_path))


def _alpha_prefix(s: str) -> str:
    return "".join(takewhile(str.isalpha, s))


def _common_prefix(strings: list[str]) -> str:
    if not strings:
        return ""
    shortest = min(strings, key=len)
    for i, ch in enumerate(shortest):
        if any(s[i] != ch for s in strings):
            return shortest[:i]
    return shortest


def derive_title(sample_names: tuple[str, ...]) -> tuple[str, str]:
    """Return (title, site_name) given the sample names.

    Site name is the longest alphabetic prefix shared across all sample names,
    stopping at the first non-alpha character in any name. Falls back to
    'Soil Report' / 'Samples' when there's no shared prefix.
    """
    if not sample_names:
        return "Soil Report", "Samples"
    common = _common_prefix([_alpha_prefix(n) for n in sample_names])
    if common:
        return f"{common} Soil Report", common
    # Single sample without a non-alpha suffix → _alpha_prefix returns the
    # full name and _common_prefix returns it too, handled by the branch above.
    # Here we only reach this for multiple samples with no shared prefix.
    return "Soil Report", "Samples"


def format_report_date(reported: str) -> str:
    """Convert '4/16/2026' to 'April 16, 2026'. Pure string math, no datetime."""
    parts = reported.split("/")
    if len(parts) != 3:
        return reported
    month_str, day, year = parts
    try:
        month_idx = int(month_str) - 1
        day_num = int(day)
        if 0 <= month_idx < 12:
            return f"{MONTHS[month_idx]} {day_num}, {year}"
    except ValueError:
        pass
    return reported


def build_report(
    selected_samples: tuple[Sample, ...],
    pdf_path: Path | None,
    title_override: str | None,
) -> BuildReportResult:
    """Assemble a Report from selected samples, deriving title and contact info.

    - Title/site name come from ``title_override`` if provided, else from the
      shared alphabetic prefix of the sample names.
    - Contact info is read from ``pdf_path`` when given; parse failures are
      soft-degraded to empty strings so a missing contact block doesn't break
      the report. The returned ``BuildReportResult`` flags such failures so
      callers can surface a warning (e.g. to stderr) while still shipping the
      report.
    - Raises ValueError only via downstream calls; this function itself does
      not raise for expected misuse.
    """
    classified = classify_all(selected_samples)
    title, site_name = derive_title(tuple(s.name for s in selected_samples))
    override = (title_override or "").strip()
    if override:
        title = override
        site_name = override.replace(" Soil Report", "").strip() or site_name
    report_date = format_report_date(selected_samples[0].reported)

    contact: tuple[str, str, str, str] = ("", "", "", "")
    contact_parse_failed = False
    contact_error: str | None = None
    if pdf_path is not None:
        try:
            contact = find_contact(pdf_path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # A missing/unparseable contact block shouldn't fail the whole
            # report — flag it for the caller to surface.
            contact_parse_failed = True
            contact_error = str(exc) or exc.__class__.__name__

    report = Report(
        title=title,
        site_name=site_name,
        report_date=report_date,
        samples=classified,
        contact_address=contact[1],
        contact_email=contact[2],
        contact_phone=contact[3],
    )
    return BuildReportResult(
        report=report,
        contact_parse_failed=contact_parse_failed,
        contact_error=contact_error,
    )
