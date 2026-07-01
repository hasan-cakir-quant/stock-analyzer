"""Value types for the growth calculator."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.services.valuations.types import Quarter

# The horizons the table renders, expressed in years.
HORIZONS: tuple[int, ...] = (1, 3, 5, 10)


@dataclass(slots=True)
class GrowthInputs:
    quarters: list[Quarter]


@dataclass(slots=True)
class MetricHorizons:
    """One metric's CAGR (or trend delta) at each horizon. None = N/A."""

    values: dict[int, Decimal | None] = field(default_factory=dict)


@dataclass(slots=True)
class GrowthResult:
    """All metrics × all horizons. Keys are stable metric identifiers."""

    metrics: dict[str, MetricHorizons] = field(default_factory=dict)
