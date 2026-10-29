"""Offline contract tests for configurable live-source adapters."""

import json


from src.ingest.changchun_drainage import (
    ChangchunDrainageAdapter,
    ChangchunDrainageConfig,
)
from src.ingest.cma_radar import CmaRadarAdapter, CmaRadarConfig
from src.service.risk_pipeline import RealtimeRiskService
from src.agent.realtime import RealtimeWeatherAgent


class FailingWeatherProvider:
    def fetch(self, latitude, longitude):
        raise TimeoutError("test weather outage")


def test_cma_json_and_cache(tmp_path):
    payload = {
        "data": {
            "values": [[[[10, 20], [30, 45]]]],
            "timestamps": ["2026-10-30T00:00:00Z"],
            "heights_m": [500],
            "origin_lat": 43.88,
            "origin_lon": 125.32,
            "cell_size_m": 500,
        }
    }
    path = tmp_path / "radar.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    cache_dir = tmp_path / "radar_cache"
    adapter = CmaRadarAdapter(CmaRadarConfig(endpoint=path.as_uri(), cache_dir=str(cache_dir)))
    result = adapter.fetch_latest(43.88, 125.32, allow_cache=False)
    assert result.is_live is True
    assert result.cube.shape == (1, 1, 2, 2)
    offline = CmaRadarAdapter(CmaRadarConfig(endpoint="", cache_dir=str(cache_dir), max_cache_age_seconds=3600))
    cached = offline.fetch_latest(43.88, 125.32)
    assert cached.source == "cma-cache"
    assert cached.is_live is False


def test_changchun_geojson_and_service_integration(tmp_path):
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [125.32, 43.88]},
                "properties": {"id": "cc-001", "积水深度": 12, "状态": "关注"},
            }
        ],
    }
    path = tmp_path / "drainage.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    drainage = ChangchunDrainageAdapter(
        ChangchunDrainageConfig(endpoint=path.as_uri(), cache_dir=str(tmp_path / "drain_cache"))
    )
    batch = drainage.fetch_latest(43.88, 125.32, allow_cache=False)
    assert batch.is_live is True
    assert batch.max_water_depth_mm == 120.0

    radar_path = tmp_path / "radar.json"
    radar_path.write_text(json.dumps({"values": [[[[45]]]], "origin_lat": 43.88, "origin_lon": 125.32}), encoding="utf-8")
    radar = CmaRadarAdapter(CmaRadarConfig(endpoint=radar_path.as_uri(), cache_dir=str(tmp_path / "radar_cache")))
    result = RealtimeRiskService(
        weather_agent=RealtimeWeatherAgent(FailingWeatherProvider()),
        radar_adapter=radar,
        drainage_adapter=drainage,
    ).run(43.88, 125.32, rainfall_mm=[10, 30, 20])
    assert result["sources"]["radar"]["source"] == "cma-authorised"
    assert result["sources"]["drainage"]["source"] == "changchun-configured"
    assert result["impact"]["observed_water_depth_mm"] == 120.0


def test_service_marks_missing_municipal_feed():
    result = RealtimeRiskService(
        weather_agent=RealtimeWeatherAgent(FailingWeatherProvider()),
        use_environment_sources=False,
    ).run(43.88, 125.32, rainfall_mm=[10, 30, 20])
    assert result["sources"]["drainage"]["source"] == "no-configured-feed"
    assert result["sources"]["drainage"]["is_live"] is False
