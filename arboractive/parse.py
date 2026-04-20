"""Parse UConn Soil Nutrient Analysis Laboratory PDFs into Sample objects."""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from .models import Sample


def _find(pattern: str, text: str, field: str, sample_name: str | None = None) -> str:
    m = re.search(pattern, text)
    if m is None:
        ctx = f" in sample {sample_name!r}" if sample_name else ""
        raise ValueError(f"Could not find {field}{ctx}")
    return m.group(1)


def _parse_page(text: str) -> Sample | None:
    """Return a Sample if the page contains a sample header, else None."""
    if "Sample Name:" not in text or "Soil pH" not in text:
        return None

    name = _find(r"Sample Name:\s*(\S+)", text, "sample name")
    lab_number = _find(r"Lab Number:\s*(\d+)", text, "lab number", name)
    received = _find(r"Received:\s*(\S+)", text, "received date", name)
    reported = _find(r"Reported:\s*(\S+)", text, "reported date", name)

    ph = float(_find(r"Soil pH \(1:1, H2O\)\s+(\d+\.?\d*)", text, "pH", name))
    calcium = float(_find(r"Calcium\s+(\d+\.?\d*)\s*lbs/acre", text, "calcium", name))
    magnesium = float(_find(r"Magnesium\s+(\d+\.?\d*)\s*lbs/acre", text, "magnesium", name))
    potassium = float(_find(r"Potassium\s+(\d+\.?\d*)\s*lbs/acre", text, "potassium", name))
    phosphorus = float(_find(r"Phosphorus\s+(\d+\.?\d*)\s*lbs/acre", text, "phosphorus", name))
    organic = float(_find(r"%\s*Organic Matter\s+(\d+\.?\d*)", text, "organic matter", name))
    cec = float(
        _find(
            r"Est\. Cation Exch\. Capacity \(meq/100g\s+(\d+\.?\d*)",
            text,
            "CEC",
            name,
        )
    )

    return Sample(
        name=name,
        lab_number=lab_number,
        received=received,
        reported=reported,
        ph=ph,
        calcium_lbs_acre=calcium,
        magnesium_lbs_acre=magnesium,
        potassium_lbs_acre=potassium,
        phosphorus_lbs_acre=phosphorus,
        organic_matter_pct=organic,
        cec_meq_100g=cec,
    )


def parse_pdf(path: str | Path) -> tuple[Sample, ...]:
    """Extract all samples from a UConn lab PDF, in page order."""
    samples: list[Sample] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            sample = _parse_page(text)
            if sample is not None:
                samples.append(sample)
    return tuple(samples)


def find_contact(path: str | Path) -> tuple[str, str, str, str]:
    """Extract (name, address, email, phone) from the Prepared For block.

    The PDF has 'Prepared For' and 'Sample Information' as side-by-side columns,
    so pdfplumber extracts them concatenated on each line. We anchor on the
    left-column values (they always come first on their line).
    """
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text() or ""

    email_m = re.search(r"([\w.+-]+@[\w.-]+\.\w+)", text)
    phone_m = re.search(r"(8\d{2}[.\-]?\d{3}[.\-]?\d{4})", text)

    # Street and city/state/zip may share a line with the right-column headers.
    # Match a leading "<number> <words> <Rd|St|Ave|Dr|Ln|Blvd|Way>" on a line.
    street_m = re.search(
        r"^(\d+\s+(?:[A-Z][a-z]+\s+)+(?:Rd|St|Ave|Dr|Ln|Blvd|Way|Street|Road|Avenue|Drive|Lane|Boulevard))\b",
        text,
        re.MULTILINE,
    )
    city_m = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}\s+\d{5})", text)
    # Name is the first line after 'Prepared For:' but that line contains the
    # right-column header too. Take the first two alpha tokens.
    name_m = re.search(r"Prepared For:[^\n]*\n([A-Z][a-z]+\s+[A-Z][a-z]+)", text)

    address_parts: list[str] = []
    if street_m:
        address_parts.append(street_m.group(1).strip())
    if city_m:
        address_parts.append(city_m.group(1).strip())
    address = ", ".join(address_parts)

    return (
        (name_m.group(1).strip() if name_m else ""),
        address,
        (email_m.group(1) if email_m else ""),
        (phone_m.group(1) if phone_m else ""),
    )
