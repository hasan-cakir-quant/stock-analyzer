"""Growth metrics — CAGRs and trend deltas across 1Y / 3Y / 5Y / 10Y horizons."""

from typing import Any

from app.services.growth.calculator import compute_growth
from app.services.growth.types import HORIZONS, GrowthInputs, GrowthResult, MetricHorizons


def to_payload(result: GrowthResult) -> dict[str, Any]:
    """Serialise a `GrowthResult` into a JSON-friendly dict.

    Each metric maps to a horizon dict like `{"1Y": 0.12, "3Y": 0.10,
    "5Y": null, "10Y": null}` — null is the "N/A" surface the UI renders.
    """
    return {
        "horizons": [f"{y}Y" for y in HORIZONS],
        "metrics": {
            metric_id: {
                f"{y}Y": (float(v) if v is not None else None)
                for y, v in horizons.values.items()
            }
            for metric_id, horizons in result.metrics.items()
        },
    }


__all__ = [
    "HORIZONS",
    "GrowthInputs",
    "GrowthResult",
    "MetricHorizons",
    "compute_growth",
    "to_payload",
]
