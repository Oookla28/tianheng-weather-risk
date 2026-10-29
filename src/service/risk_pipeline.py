"""把实时天气、雷达体素和排水推演编排成一个后端响应。"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..agent.realtime import RealtimeWeatherAgent
from ..drainage.simulator import DrainageSimulator
from ..radar.voxel import RadarVoxelCube


class RealtimeRiskService:
    """Single-call service used by an API or a private frontend adapter."""

    def __init__(
        self,
        weather_agent: RealtimeWeatherAgent | None = None,
        drainage: DrainageSimulator | None = None,
    ) -> None:
        self.weather_agent = weather_agent or RealtimeWeatherAgent()
        self.drainage = drainage or DrainageSimulator()

    def run(
        self,
        latitude: float,
        longitude: float,
        radar_cube: RadarVoxelCube | None = None,
        rainfall_mm: list[float] | np.ndarray | None = None,
        impervious_ratio: float = 0.65,
    ) -> dict[str, Any]:
        cube = radar_cube or RadarVoxelCube.synthetic(origin_lat=latitude, origin_lon=longitude)
        radar_score = cube.convective_score()
        risk = self.weather_agent.assess(latitude, longitude, radar_score=radar_score, terrain_susceptibility=0.58)
        latest_precip = float(risk["snapshot"]["precipitation_mm"])
        rain = np.asarray(rainfall_mm if rainfall_mm is not None else [latest_precip, latest_precip * 1.15, latest_precip * 0.9, latest_precip * 0.65], dtype=float)
        simulations = self.drainage.counterfactuals(rain, impervious_ratio=impervious_ratio)
        baseline = simulations["baseline"]
        impact = {
            "peak_overflow_mm": baseline.peak_overflow_mm,
            "flooded_area_fraction": baseline.total_flooded_area_fraction,
            "risk_level": "极高" if baseline.peak_overflow_mm >= 20 else "高" if baseline.peak_overflow_mm >= 8 else "中" if baseline.peak_overflow_mm > 0 else "低",
        }
        return {
            "location": {"latitude": latitude, "longitude": longitude},
            "risk": risk,
            "radar": cube.to_dict(include_values=False),
            "impact": impact,
            "counterfactuals": {name: result.to_dict() for name, result in simulations.items()},
            "disclaimer": "研究与决策支持结果，不构成官方预警。",
        }


__all__ = ["RealtimeRiskService"]
