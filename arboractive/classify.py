"""Apply threshold specs to samples to produce ClassifiedSample."""

from __future__ import annotations

from .models import ClassifiedSample, Sample, TieredValue
from .thresholds import SPECS, format_value, tier_for


def classify(sample: Sample) -> ClassifiedSample:
    pairs: list[tuple[str, TieredValue]] = []
    for spec in SPECS:
        raw = float(getattr(sample, spec.attr))
        tv = TieredValue(
            raw=raw,
            formatted=format_value(spec, raw),
            unit=spec.unit,
            tier=tier_for(spec, raw),
        )
        pairs.append((spec.label, tv))
    return ClassifiedSample(sample=sample, nutrients=tuple(pairs))


def classify_all(samples: tuple[Sample, ...]) -> tuple[ClassifiedSample, ...]:
    return tuple(classify(s) for s in samples)
