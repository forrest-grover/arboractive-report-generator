# arboractive-report-generator

Deterministic CLI tool that ingests a UConn Soil Nutrient Analysis Laboratory PDF
and produces a branded ArborActive soil report as a single self-contained HTML
file.

Same input always yields byte-identical HTML output.

## Features

- Parses multi-page UConn lab PDFs (Modified Morgan extraction) using regex
  patterns anchored to text labels.
- Classifies seven analytes (pH, Ca, Mg, K, P, Organic Matter, CEC) into five
  tiers (`VERY_LOW`, `LOW`, `GOOD`, `HIGH`, `VERY_HIGH`) using thresholds
  sourced from the [UConn SNAL agronomic crops page][uconn-thresholds].
- Renders a branded HTML comparison table with per-nutrient threshold bars:
  five balanced zones (red/amber/green/amber/red, 20% each) and a
  tier-relative value marker. Units shown on every row.
- Single self-contained HTML: inline CSS, inline SVG, base64-embedded PNG
  logos. No network fetches, no web fonts, no external assets.
- **Fully deterministic**: frozen dataclasses, tuple iteration only, no
  `datetime.now()`, no RNG, integer SVG coordinates.

[uconn-thresholds]: https://soiltesting.cahnr.uconn.edu/soil-test-results-for-agronomic-crops/

## Requirements

- Python 3.11+
- `pdfplumber`

## Install

```bash
pip install -e .
```

## Usage

```bash
python -m arboractive report INPUT.pdf \
    --sample "SampleNameA" \
    --sample "SampleNameB" \
    [--title "Custom Report Title"] \
    [--out output.html]
```

Omit `--out` to write HTML to stdout (pipe-friendly).

Sample names are matched case-insensitively against the sample headers in the
PDF but stored verbatim for display. When two or more samples share a leading
alphabetic prefix (e.g. `SiteA(front)` and `SiteB(back)` share `Site`), the
title defaults to `"Site Soil Report"`.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Usage error (missing required flag) |
| 2 | Input PDF not found or unreadable |
| 3 | A requested `--sample` was not found in the PDF |
| 4 | PDF parse failure |

## Project layout

```
arboractive/
  __init__.py      package metadata
  __main__.py      entry point for `python -m arboractive`
  cli.py           argparse + orchestration
  parse.py         PDF text extraction (pdfplumber + regex)
  thresholds.py    ThresholdSpec table + tier-classifier dispatch
  classify.py      Sample -> ClassifiedSample
  render.py        ClassifiedSamples -> HTML (inline CSS, inline SVG)
  models.py        frozen dataclasses shared between modules
  assets/          brand PNGs (base64-inlined at render time)
tests/
  test_parse.py        synthetic UConn-layout text
  test_classify.py     tier-boundary fixtures
  test_determinism.py  byte-identical render smoke test
```

## Development

Run the full quality sweep:

```bash
ruff check arboractive tests
black --check arboractive tests
mypy arboractive tests
pylint arboractive tests
python -m pytest tests -q
```

Tool configs live in `pyproject.toml`:
- `ruff` — isort, pyflakes, pyupgrade, bugbear, simplify, ruff rules
- `black` — line length 100
- `mypy` — `strict = true`
- `pylint` — 10.00/10 clean on current code

## Determinism guarantees

- All inter-module data is carried in `frozen=True` dataclasses backed by
  tuples. No dicts or sets cross module boundaries.
- SVG coordinates are integers or fixed-precision decimals rounded to two
  places — no floating-point jitter.
- Dates in the PDF are kept as raw strings; the renderer formats them via
  pure string math. No `datetime.now()`, no locale-dependent formatting.
- Logo PNGs are base64-encoded on first access and cached with `lru_cache`.
  Same bytes → same base64 → same HTML output.

Regenerate twice and diff to confirm:

```bash
python -m arboractive report in.pdf --sample "A" --out out1.html
python -m arboractive report in.pdf --sample "A" --out out2.html
diff out1.html out2.html   # must be empty
```
