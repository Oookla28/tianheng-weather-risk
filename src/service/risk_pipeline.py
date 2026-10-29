"""Compose live weather, CMA radar and Changchun drainage evidence."""

from __future__ import annotations

import os
from typing import Any

import numpy as np

from ..agent.realtime import RealtimeWeatherAgent
from ..drainage.simulator import DrainageSimulator
from ..ingest.changchun_drainage import ChangchunDrainageAdapter, DrainageDataError, DrainageSourceUnavailable
from ..ingest.cma_radar import CmaRadarAdapter, RadarDataError, RadarSourceUnavailable
from ..radar.voxel import RadarVoxelCube


class RealtimeRiskService:
    """Single-call backend service with live-source adapters and safe fallback.

    Set ``CMA_RADAR_ENDPOINT`` and ``CHANGCHUN_DRAINAGE_ENDPOINT`` to enable
    authorised live feeds.  The service never silently labels synthetic or
    cached data as live: ``sources`` and each provider's provenance are returned
    in the serializable response.
    """

    def __init__(
        self,
        weather_agent: RealtimeWeatherAgent | None = None,
        drainage: DrainageSimulator | None = None,
        radar_adapter: CmaRadarAdapter | None = None,
        drainage_adapter: ChangchunDrainageAdapter | None = None,
        use_environment_sources: bool | None = None,
    ) -> None:
        self.weather_agent = weather_agent or RealtimeWeatherAgent()
        self.drainage = drainage or DrainageSimulator()
        self.radar_adapter = radar_adapter
        self.drainage_adapter = drainage_adapter
        if use_environment_sources is None:
            use_environment_sources = bool(os.getenv("CMA_RADAR_ENDPOINT") or os.getenv("CHANGCHUN_DRAINAGE_ENDPOINT"))
        if use_environment_sources:
            if self.radar_adapter is None:
                self.radar_adapter = CmaRadarAdapter()
            if self.drainage_adapter is None:
                self.drainage_adapter = ChangchunDrainageAdapter()

    @classmethod
    def from_environment(cls, **kwargs: Any) -> "RealtimeRiskService":
        """Build a service that reads configured live endpoints and tokens."""

        kwargs["use_environment_sources"] = True
        return cls(**kwargs)

    def run(
        self,
        latitude: float,
        longitude: float,
        radar_cube: RadarVoxelCube | None = None,
        rainfall_mm: list[float] | np.ndarray | None = None,
        impervious_ratio: float = 0.65,
        *,
        use_live_sources: bool = True,
    ) -> dict[str, Any]:
        source_status: dict[str, Any] = {}
        radar_result = None
        if radar_cube is None and use_live_sources and self.radar_adapter is not None:
            try:
                radar_result = self.radar_adapter.fetch_latest(latitude, longitude)
                cube = radar_result.cube
                source_status["radar"] = radar_result.to_dict()
            except (RadarSourceUnavailable, RadarDataError) as exc:
                cube = RadarVoxelCube.synthetic(origin_lat=latitude, origin_lon=longitude)
                source_status["radar"] = {
                    "source": "synthetic-fallback",
                    "is_live": False,
                    "provenance": {"reason": str(exc), "label_quality": "synthetic"},
                }
        else:
            cube = radar_cube or RadarVoxelCube.synthetic(origin_lat=latitude, origin_lon=longitude)
            source_status["radar"] = {
                "source": cube.source,
                "is_live": cube.source.startswith("cma-"),
                "provenance": {"label_quality": "real" if cube.source.startswith("cma-") else "synthetic"},
            }

        radar_score = cube.convective_score()
        risk = self.weather_agent.assess(
            latitude,
            longitude,
            radar_score=radar_score,
            terrain_susceptibility=0.58,
        )
        source_status["weather"] = {
            "source": risk["snapshot"]["source"],
            "is_live": bool(risk["snapshot"]["is_live"]),
            "provenance": dict(risk["snapshot"].get("provenance", {})),
        }

        drainage_batch = None
        initial_storage_mm = 0.0
        if use_live_sources and self.drainage_adapter is not None:
            try:
                drainage_batch = self.drainage_adapter.fetch_latest(latitude, longitude)
                initial_storage_mm = min(float(drainage_batch.max_water_depth_mm), self.drainage.storage_limit)
                source_status["drainage"] = drainage_batch.to_dict()
            except (DrainageSourceUnavailable, DrainageDataError) as exc:
                source_status["drainage"] = {
                    "source": "no-configured-feed",
                    "is_live": False,
                    "provenance": {"reason": str(exc), "label_quality": "synthetic"},
                }
        elif self.drainage_adapter is None:
            source_status["drainage"] = {
                "source": "no-configured-feed",
                "is_live": False,
                "provenance": {
                    "reason": "CHANGCHUN_DRAINAGE_ENDPOINT is not configured",
                    "label_quality": "unavailable",
                },
            }

        latest_precip = float(risk["snapshot"]["precipitation_mm"])
        rain = np.asarray(
            rainfall_mm if rainfall_mm is not None else [latest_precip, latest_precip * 1.15, latest_precip * 0.9, latest_precip * 0.65],
            dtype=float,
        )
        simulations = self.drainage.counterfactuals(
            rain,
            impervious_ratio=impervious_ratio,
            initial_storage_mm=initial_storage_mm,
        )
        baseline = simulations["baseline"]
        observed_depth = float(drainage_batch.max_water_depth_mm) if drainage_batch else 0.0
        observed_fraction = float(drainage_batch.flooded_fraction) if drainage_batch else 0.0
        model_risk_level = "极高" if baseline.peak_overflow_mm >= 20 else "高" if baseline.peak_overflow_mm >= 8 else "中" if baseline.peak_overflow_mm > 0 else "低"
        if observed_depth >= 200 or observed_fraction >= 0.5:
            impact_level = "极高"
        elif observed_depth >= 100 or observed_fraction >= 0.25:
            impact_level = "高"
        else:
            impact_level = model_risk_level
        impact = {
            "peak_overflow_mm": baseline.peak_overflow_mm,
            "flooded_area_fraction": baseline.total_flooded_area_fraction,
            "risk_level": impact_level,
            "model_risk_level": model_risk_level,
            "observed_water_depth_mm": observed_depth,
            "observed_flooded_fraction": observed_fraction,
        }
        return {
            "location": {"latitude": latitude, "longitude": longitude},
            "risk": risk,
            "radar": cube.to_dict(include_values=False),
            "impact": impact,
            "sources": source_status,
            "counterfactuals": {name: result.to_dict() for name, result in simulations.items()},
            "disclaimer": "研究与决策支持结果，不构成官方预警；实时数据须使用授权接口。",
        }


__all__ = ["RealtimeRiskService"]
