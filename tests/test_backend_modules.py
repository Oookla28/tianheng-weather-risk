"""Offline acceptance tests for the public backend modules."""

import json

from src.agent.realtime import RealtimeWeatherAgent
from src.drainage.simulator import DrainageSimulator
from src.radar.voxel import RadarVoxelCube
from src.service.risk_pipeline import RealtimeRiskService


class FailingProvider:
    def fetch(self, latitude, longitude):
        raise TimeoutError("simulated provider outage")


def test_realtime_agent_fallback_is_explicit():
    snapshot = RealtimeWeatherAgent(FailingProvider()).snapshot(43.88, 125.32)
    assert snapshot.source == "deterministic-fallback"
    assert snapshot.is_live is False
    assert snapshot.provenance["label_quality"] == "synthetic"


def test_radar_voxel_contract_and_nowcast():
    cube = RadarVoxelCube.synthetic(n_times=4, n_heights=3, n_rows=12, n_cols=12, seed=7)
    assert cube.shape == (4, 3, 12, 12)
    assert len(cube.summary()) == 4
    assert 0.0 <= cube.convective_score() <= 1.0
    assert cube.nowcast(horizons=3).shape == (3, 3, 12, 12)


def test_drainage_counterfactual_ordering():
    results = DrainageSimulator().counterfactuals([40, 80, 100, 60], impervious_ratio=0.7)
    assert results["early_pumping"].peak_overflow_mm < results["baseline"].peak_overflow_mm
    assert results["blocked_inlets"].peak_overflow_mm > results["baseline"].peak_overflow_mm
    assert results["rainfall_minus_20pct"].peak_overflow_mm < results["baseline"].peak_overflow_mm


def test_unified_service_is_json_serializable():
    cube = RadarVoxelCube.synthetic(n_times=3, n_heights=2, n_rows=8, n_cols=8, seed=5)
    result = RealtimeRiskService(weather_agent=RealtimeWeatherAgent(FailingProvider())).run(
        43.88, 125.32, radar_cube=cube, rainfall_mm=[12, 40, 20], impervious_ratio=0.7
    )
    json.dumps(result, ensure_ascii=False)
    assert result["risk"]["snapshot"]["is_live"] is False
    assert result["radar"]["shape"] == [3, 2, 8, 8]
    assert set(result["counterfactuals"]) == {
        "baseline",
        "early_pumping",
        "blocked_inlets",
        "rainfall_minus_20pct",
    }
