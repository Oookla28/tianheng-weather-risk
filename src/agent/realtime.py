"""轻量实时天气 Agent。

The agent deliberately keeps the provider boundary small: a live Open-Meteo
request can be replaced by an authorised CMA adapter without changing risk
scoring or downstream services.  Network failures fall back to a deterministic
snapshot and are recorded in ``provenance`` so a demo cannot be mistaken for
an official warning.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class WeatherSnapshot:
    """One location's current weather context in stable SI units."""

    latitude: float
    longitude: float
    observed_at: str
    temperature_c: float
    precipitation_mm: float
    precipitation_probability: float
    wind_speed_kmh: float
    humidity_percent: float
    source: str
    is_live: bool
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WeatherProvider(Protocol):
    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        """Return the latest snapshot or raise a provider error."""


class OpenMeteoProvider:
    """No-key weather adapter for demonstrations and reproducible tests."""

    def __init__(self, timeout_seconds: float = 5.0, user_agent: str = "tianheng-weather-impact/0.2") -> None:
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        params = {
            "latitude": f"{latitude:.5f}",
            "longitude": f"{longitude:.5f}",
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "hourly": "precipitation_probability",
            "forecast_days": "1",
            "timezone": "UTC",
        }
        url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        current = payload.get("current", {})
        hourly = payload.get("hourly", {})
        probabilities = hourly.get("precipitation_probability") or [0]
        probability = float(probabilities[0] or 0.0) / 100.0
        return WeatherSnapshot(
            latitude=float(latitude),
            longitude=float(longitude),
            observed_at=str(current.get("time") or _utc_now()),
            temperature_c=float(current.get("temperature_2m") or 0.0),
            precipitation_mm=float(current.get("precipitation") or 0.0),
            precipitation_probability=max(0.0, min(1.0, probability)),
            wind_speed_kmh=float(current.get("wind_speed_10m") or 0.0),
            humidity_percent=float(current.get("relative_humidity_2m") or 0.0),
            source="open-meteo",
            is_live=True,
            provenance={"endpoint": "https://api.open-meteo.com/v1/forecast", "license": "CC BY 4.0"},
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def deterministic_fallback(latitude: float, longitude: float, reason: str = "provider_unavailable") -> WeatherSnapshot:
    """Create stable synthetic context for offline operation.

    Coordinates perturb the values slightly to keep multiple locations useful
    while remaining deterministic and clearly marked as synthetic.
    """

    phase = abs(math.sin(float(latitude) * 0.71 + float(longitude) * 0.13))
    return WeatherSnapshot(
        latitude=float(latitude),
        longitude=float(longitude),
        observed_at=_utc_now(),
        temperature_c=17.0 + 8.0 * phase,
        precipitation_mm=4.0 + 24.0 * phase,
        precipitation_probability=min(0.95, 0.35 + 0.6 * phase),
        wind_speed_kmh=12.0 + 32.0 * phase,
        humidity_percent=64.0 + 30.0 * phase,
        source="deterministic-fallback",
        is_live=False,
        provenance={"reason": reason, "label_quality": "synthetic"},
    )


class RealtimeWeatherAgent:
    """Location-first risk agent with explicit confidence and evidence."""

    def __init__(self, provider: WeatherProvider | None = None, allow_fallback: bool = True) -> None:
        self.provider = provider or OpenMeteoProvider()
        self.allow_fallback = allow_fallback

    def snapshot(self, latitude: float, longitude: float) -> WeatherSnapshot:
        try:
            return self.provider.fetch(latitude, longitude)
        except Exception as exc:
            if not self.allow_fallback:
                raise
            return deterministic_fallback(latitude, longitude, reason=f"{type(exc).__name__}: {exc}")

    def assess(
        self,
        latitude: float,
        longitude: float,
        radar_score: float = 0.0,
        terrain_susceptibility: float = 0.5,
    ) -> dict[str, Any]:
        """Return a human-readable impact probability and machine evidence.

        The score is a transparent baseline. It is intentionally not labelled
        as an official warning and is suitable for model comparison or a live
        product prototype until calibrated with authorised local observations.
        """

        snapshot = self.snapshot(latitude, longitude)
        rain_signal = min(1.0, snapshot.precipitation_mm / 35.0)
        wind_signal = min(1.0, snapshot.wind_speed_kmh / 70.0)
        weather_signal = 0.62 * rain_signal + 0.23 * snapshot.precipitation_probability + 0.15 * wind_signal
        risk_probability = max(0.0, min(1.0, 0.58 * weather_signal + 0.42 * float(terrain_susceptibility) + 0.18 * float(radar_score)))
        level = "极高" if risk_probability >= 0.8 else "高" if risk_probability >= 0.6 else "中" if risk_probability >= 0.35 else "低"
        confidence = 0.82 if snapshot.is_live else 0.48
        reasons = []
        if rain_signal >= 0.55:
            reasons.append("短时降水偏强")
        if snapshot.precipitation_probability >= 0.6:
            reasons.append("降水概率较高")
        if float(terrain_susceptibility) >= 0.65:
            reasons.append("地形汇流易涝")
        if float(radar_score) >= 0.6:
            reasons.append("雷达回波显示对流增强")
        return {
            "location": {"latitude": float(latitude), "longitude": float(longitude)},
            "snapshot": snapshot.to_dict(),
            "risk_probability": round(risk_probability, 4),
            "risk_level": level,
            "confidence": confidence,
            "main_reasons": reasons or ["当前气象信号较弱"],
            "evidence": {
                "method": "transparent_baseline_v1",
                "radar_score": float(radar_score),
                "terrain_susceptibility": float(terrain_susceptibility),
                "official_warning": False,
            },
        }


__all__ = ["WeatherProvider", "WeatherSnapshot", "OpenMeteoProvider", "RealtimeWeatherAgent", "deterministic_fallback"]
