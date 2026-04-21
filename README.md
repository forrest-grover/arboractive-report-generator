# arboractive-report-generator

Ingests a UConn Soil Nutrient Analysis Laboratory PDF and emits a branded
ArborActive soil report (self-contained HTML or PDF) comparing up to two
samples side-by-side.

## Requirements

- Python 3.11+
- `pdfplumber` (PDF text extraction)
- `weasyprint` (optional, required only for PDF output)

## Install

```bash
pip install -e .
```

## Usage

### GUI (recommended for non-technical users)

```bash
python -m arboractive gui
```

Opens a window with three steps:

1. Click **Select PDF...** and pick the UConn lab PDF from your computer.
2. Tick up to two samples from the list (more than two are disabled).
3. Click **Save as HTML...** or **Save as PDF...** — a native save dialog
   picks the destination.

Optional title override available. Status bar and dialogs report errors.

### Command line

```bash
python -m arboractive report INPUT.pdf \
    --sample "SampleNameA" \
    --sample "SampleNameB" \
    [--title "Custom Report Title"] \
    [--out output.html|output.pdf]
```

The output format is inferred from the `--out` extension: `.pdf` renders a
PDF (via `weasyprint`), anything else writes HTML. Omit `--out` to write HTML
to stdout (pipe-friendly).

At most **2 samples per report**. The layout is designed for side-by-side
comparison; extra samples are rejected at the CLI with exit code 1.

Sample names are matched case-insensitively against the sample headers in the
PDF but stored verbatim for display. When two or more samples share a leading
alphabetic prefix (e.g. `SiteA(front)` and `SiteB(back)` share `Site`), the
title defaults to `"Site Soil Report"`.

If the contact block in the PDF cannot be parsed, the report still renders
with empty contact fields and a warning is printed to stderr.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Usage error (missing required flag) |
| 2 | Input PDF not found or unreadable |
| 3 | A requested `--sample` was not found in the PDF |
| 4 | PDF parse failure |
