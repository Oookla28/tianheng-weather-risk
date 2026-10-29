"""可解释的城市排水数字孪生基线。

This is a screening model for a competition prototype. It conserves rainfall
volume at grid-cell level, accounts for imperviousness and drainage capacity,
and exposes counterfactuals such as earlier pumping or blocked inlets.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

import numpy as np


@dataclass(frozen=True)
class DrainageStep:
    minute: int
    rainfall_mm: float
    runoff_mm: float
    capacity_mm: float
    storage_mm: float
    overflow_mm: float
    flooded_area_fraction: float
    risk_level: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DrainageResult:
    steps: list[DrainageStep]
    peak_overflow_mm: float
    peak_storage_mm: float
    total_flooded_area_fraction: float
    intervention: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [step.to_dict() for step in self.steps],
            "peak_overflow_mm": self.peak_overflow_mm,
            "peak_storage_mm": self.peak_storage_mm,
            "total_flooded_area_fraction": self.total_flooded_area_fraction,
            "intervention": self.intervention,
        }


class DrainageSimulator:
    """Grid-aggregated reservoir model with deterministic counterfactuals."""

    def __init__(self, base_capacity_mm_per_step: float = 8.0, storage_limit_mm: float = 35.0) -> None:
        if base_capacity_mm_per_step <= 0 or storage_limit_mm <= 0:
            raise ValueError("capacity and storage limit must be positive")
        self.base_capacity = float(base_capacity_mm_per_step)
        self.storage_limit = float(storage_limit_mm)

    def simulate(
        self,
        rainfall_mm: np.ndarray | list[float],
        impervious_ratio: float | np.ndarray = 0.65,
        capacity_multiplier: float = 1.0,
        initial_storage_mm: float = 0.0,
        intervention: Mapping[str, Any] | None = None,
    ) -> DrainageResult:
        rainfall = np.asarray(rainfall_mm, dtype=float).reshape(-1)
        if rainfall.size == 0:
            raise ValueError("rainfall_mm cannot be empty")
        impervious = float(np.clip(np.asarray(impervious_ratio, dtype=float).mean(), 0.0, 1.0))
        capacity_multiplier = max(0.0, float(capacity_multiplier))
        storage = max(0.0, float(initial_storage_mm))
        steps: list[DrainageStep] = []
        for idx, rain in enumerate(rainfall):
            rain = max(0.0, float(rain))
            runoff = rain * (0.22 + 0.78 * impervious)
            capacity = self.base_capacity * capacity_multiplier
            storage += runoff - capacity
            overflow = max(0.0, storage - self.storage_limit)
            storage = min(self.storage_limit, max(0.0, storage))
            flooded_fraction = float(np.clip(overflow / max(self.storage_limit, 1e-6), 0.0, 1.0))
            level = "极高" if flooded_fraction >= 0.65 else "高" if flooded_fraction >= 0.35 else "中" if flooded_fraction >= 0.1 else "低"
            steps.append(DrainageStep(idx * 5, rain, runoff, capacity, storage, overflow, flooded_fraction, level))
        return DrainageResult(
            steps=steps,
            peak_overflow_mm=max(step.overflow_mm for step in steps),
            peak_storage_mm=max(step.storage_mm for step in steps),
            total_flooded_area_fraction=float(np.clip(sum(step.flooded_area_fraction for step in steps), 0.0, 1.0)),
            intervention=dict(intervention or {}),
        )

    def counterfactuals(
        self,
        rainfall_mm: np.ndarray | list[float],
        impervious_ratio: float | np.ndarray = 0.65,
        scenarios: Mapping[str, Mapping[str, Any]] | None = None,
        initial_storage_mm: float = 0.0,
    ) -> dict[str, DrainageResult]:
        """Run baseline plus named interventions with identical rainfall."""

        scenarios = scenarios or {
            "baseline": {"capacity_multiplier": 1.0},
            "early_pumping": {"capacity_multiplier": 1.35},
            "blocked_inlets": {"capacity_multiplier": 0.62},
            "rainfall_minus_20pct": {"rainfall_scale": 0.8, "capacity_multiplier": 1.0},
        }
        output: dict[str, DrainageResult] = {}
        base = np.asarray(rainfall_mm, dtype=float)
        for name, settings in scenarios.items():
            rain = base * float(settings.get("rainfall_scale", 1.0))
            output[name] = self.simulate(
                rain,
                impervious_ratio,
                capacity_multiplier=float(settings.get("capacity_multiplier", 1.0)),
                initial_storage_mm=float(initial_storage_mm),
                intervention={"name": name, **dict(settings)},
            )
        return output


__all__ = ["DrainageSimulator", "DrainageResult", "DrainageStep"]
