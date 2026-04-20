"""CLI entry point: parse → classify → analyze → render."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .classify import classify_all
from .models import Report
from .parse import find_contact, parse_pdf
from .render import _format_report_date, render

MAX_SAMPLES_PER_REPORT = 2

# Fixed value for weasyprint's PDF CreationDate metadata. Any constant works;
# the point is that repeated runs with the same input produce byte-identical
# PDFs. weasyprint (and most reproducible-build tooling) honors this env var.
_DETERMINISTIC_SOURCE_DATE_EPOCH = "0"


def _write_pdf(html: str, out_path: Path) -> None:
    """Render HTML to a deterministic PDF at out_path."""
    os.environ["SOURCE_DATE_EPOCH"] = _DETERMINISTIC_SOURCE_DATE_EPOCH
    # Lazy import so pure-HTML workflows don't pay weasyprint startup cost.
    from weasyprint import HTML  # pylint: disable=import-outside-toplevel

    HTML(string=html).write_pdf(target=str(out_path))


def _derive_title(sample_names: tuple[str, ...]) -> tuple[str, str]:
    """Return (title, site_name) given the sample names.

    If names share a common prefix of alphabetic chars only (stopping at the
    first non-alpha), use that prefix as the site name.
    Otherwise fall back to 'Soil Report' / the first sample's name.
    """
    if not sample_names:
        return "Soil Report", "Samples"
    if len(sample_names) == 1:
        name = sample_names[0]
        site = _alpha_prefix(name) or name
        return f"{site} Soil Report", site

    prefixes = [_alpha_prefix(n) for n in sample_names]
    common = _common_prefix(prefixes)
    if common:
        return f"{common} Soil Report", common
    return "Soil Report", "Samples"


def _alpha_prefix(s: str) -> str:
    out = []
    for ch in s:
        if ch.isalpha():
            out.append(ch)
        else:
            break
    return "".join(out)


def _common_prefix(strings: list[str]) -> str:
    if not strings:
        return ""
    shortest = min(strings, key=len)
    for i, ch in enumerate(shortest):
        if any(s[i] != ch for s in strings):
            return shortest[:i]
    return shortest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arboractive",
        description="Turn UConn soil lab PDFs into branded ArborActive reports.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    rp = sub.add_parser("report", help="Generate a soil report HTML from a PDF.")
    rp.add_argument("input_pdf", metavar="input.pdf", help="Path to UConn lab PDF")
    rp.add_argument(
        "--sample",
        action="append",
        dest="samples",
        metavar="NAME",
        required=True,
        help="Sample name as it appears in the PDF (repeatable)",
    )
    rp.add_argument("--title", default=None, help="Override report title")
    rp.add_argument(
        "--out",
        default=None,
        metavar="OUTPUT",
        help="Output path. Extension selects format: .pdf renders a PDF, "
        "any other extension (or stdout, if omitted) writes HTML.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command != "report":
        parser.print_help()
        return 1

    if len(args.samples) > MAX_SAMPLES_PER_REPORT:
        print(
            f"error: at most {MAX_SAMPLES_PER_REPORT} samples per report "
            f"(got {len(args.samples)})",
            file=sys.stderr,
        )
        return 1

    pdf_path = Path(args.input_pdf)
    if not pdf_path.is_file():
        print(f"error: PDF not found: {pdf_path}", file=sys.stderr)
        return 2

    try:
        all_samples = parse_pdf(pdf_path)
        contact_name, address, email, phone = find_contact(pdf_path)
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Surface any parse/IO failure as a clean CLI error code.
        print(f"error: PDF parse failure: {e}", file=sys.stderr)
        return 4

    if not all_samples:
        print("error: no samples found in PDF", file=sys.stderr)
        return 4

    available = {s.name.casefold(): s for s in all_samples}
    selected = []
    for requested in args.samples:
        match = available.get(requested.casefold())
        if match is None:
            print(
                f"error: sample {requested!r} not found in PDF.\n"
                f"Available: {', '.join(s.name for s in all_samples)}",
                file=sys.stderr,
            )
            return 3
        selected.append(match)

    classified = classify_all(tuple(selected))

    title, site_name = _derive_title(tuple(s.name for s in selected))
    if args.title:
        title = args.title
        site_name = args.title.replace(" Soil Report", "").strip() or site_name

    report_date = _format_report_date(selected[0].reported)

    report = Report(
        title=title,
        site_name=site_name,
        report_date=report_date,
        samples=classified,
        contact_name=contact_name,
        contact_address=address,
        contact_email=email,
        contact_phone=phone,
    )

    html = render(report)
    if args.out:
        out_path = Path(args.out)
        if out_path.suffix.lower() == ".pdf":
            _write_pdf(html, out_path)
        else:
            out_path.write_text(html, encoding="utf-8")
    else:
        sys.stdout.write(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
