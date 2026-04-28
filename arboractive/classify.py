"""Apply threshold specs to samples to produce ClassifiedSample.

Nutrients flow through the generic ``SPECS`` loop. Toxic metals (Al, Pb) use
the separate ``TOXICS`` table with three-band GOOD/HIGH/VERY_HIGH semantics
(see ``thresholds.ToxicSpec``) because a 5-tier "sweet-spot-in-the-middle"
scale is semantically wrong for "lower is always better" contaminants.
"""

from __future__ import annotations

from .models import ClassifiedSample, Sample, Tier, TieredValue
from .thresholds import (
    SPECS,
    TOXICS,
    ToxicSpec,
    format_toxic_value,
    format_value,
    tier_for,
    toxic_tier_for,
)


def _toxic_tv(sample: Sample, spec: ToxicSpec) -> TieredValue:
    """Classify a toxic-metal value.

    ``None`` (lab detection-floor case for Pb) → GOOD with formatted="low"
    so the renderer can show the literal word. Numeric values pass through
    ``toxic_tier_for``.
    """
    raw_opt: float | None = getattr(sample, spec.attr)
    if raw_opt is None:
        return TieredValue(raw=0.0, formatted="low", unit=spec.unit, tier=Tier.GOOD)
    return TieredValue(
        raw=raw_opt,
        formatted=format_toxic_value(spec, raw_opt),
        unit=spec.unit,
        tier=toxic_tier_for(spec, raw_opt),
    )


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
    for tspec in TOXICS:
        pairs.append((tspec.label, _toxic_tv(sample, tspec)))
    return ClassifiedSample(sample=sample, nutrients=tuple(pairs))


def classify_all(samples: tuple[Sample, ...]) -> tuple[ClassifiedSample, ...]:
    return tuple(classify(s) for s in samples)
