"""CLI entry point: parse → classify → render."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .parse import parse_pdf
from .pipeline import build_report, write_pdf
from .render import render

MAX_SAMPLES_PER_REPORT = 2


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
    sub.add_parser("gui", help="Launch the graphical interface.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "gui":
        from .gui import run_gui  # pylint: disable=import-outside-toplevel

        run_gui()
        return 0
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

    result = build_report(tuple(selected), pdf_path, args.title)
    if result.contact_parse_failed:
        print(
            "Warning: contact block could not be parsed; contact fields left empty.",
            file=sys.stderr,
        )

    html = render(result.report)
    if args.out:
        out_path = Path(args.out)
        if out_path.suffix.lower() == ".pdf":
            write_pdf(html, out_path)
        else:
            out_path.write_text(html, encoding="utf-8")
    else:
        sys.stdout.write(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
