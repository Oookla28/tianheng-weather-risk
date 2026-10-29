"""Changchun drainage and waterlogging observation adapter.

Municipal drainage data is commonly published as CSV, JSON, or GeoJSON and
may require a city data agreement.  The adapter therefore accepts a configured
endpoint and maps common Chinese and English field names without hard-coding an
unverified public URL.  Each observation retains its source and live/cached
status so downstream risk output remains auditable.
"""

from __future__ import annotations

import csv
import io
import json
import os
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


class DrainageDataError(RuntimeError):
    """Raised when drainage observations cannot be parsed or validated."""


class DrainageSourceUnavailable(RuntimeError):
    """Raised when no live or cached drainage source is available."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class DrainageObservation:
    observation_id: str
    observed_at: str
    latitude: float
    longitude: float
    water_depth_mm: float
    status: str = "unknown"
    rainfall_mm: float | None = None
    source: str = "changchun-configured"
    is_live: bool = True
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DrainageObservationBatch:
    observations: tuple[DrainageObservation, ...]
    source: str
    is_live: bool
    retrieved_at: str
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def max_water_depth_mm(self) -> float:
        return max((item.water_depth_mm for item in self.observations), default=0.0)

    @property
    def flooded_fraction(self) -> float:
        if not self.observations:
            return 0.0
        return sum(item.water_depth_mm > 50.0 for item in self.observations) / len(self.observations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "is_live": self.is_live,
            "retrieved_at": self.retrieved_at,
            "provenance": dict(self.provenance),
            "max_water_depth_mm": self.max_water_depth_mm,
            "flooded_fraction": self.flooded_fraction,
            "observations": [item.to_dict() for item in self.observations],
        }


@dataclass(frozen=True)
class ChangchunDrainageConfig:
    endpoint: str = field(default_factory=lambda: os.getenv("CHANGCHUN_DRAINAGE_ENDPOINT", ""))
    token: str = field(default_factory=lambda: os.getenv("CHANGCHUN_DRAINAGE_TOKEN", ""))
    timeout_seconds: float = field(default_factory=lambda: float(os.getenv("CHANGCHUN_DRAINAGE_TIMEOUT", "8")))
    cache_dir: str = field(default_factory=lambda: os.getenv("CHANGCHUN_DRAINAGE_CACHE_DIR", "data/cache/changchun_drainage"))
    max_cache_age_seconds: int = field(default_factory=lambda: int(os.getenv("CHANGCHUN_DRAINAGE_MAX_CACHE_AGE", "1800")))
    depth_unit: str = field(default_factory=lambda: os.getenv("CHANGCHUN_DRAINAGE_DEPTH_UNIT", "cm"))


class ChangchunDrainageAdapter:
    """Fetch a configured Changchun observation feed and normalise its rows."""

    def __init__(self, config: ChangchunDrainageConfig | None = None) -> None:
        self.config = config or ChangchunDrainageConfig()
        self.cache_dir = Path(self.config.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_latest(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        *,
        allow_cache: bool = True,
    ) -> DrainageObservationBatch:
        if not self.config.endpoint:
            if allow_cache:
                cached = self._load_cache()
                if cached is not None:
                    return cached
            raise DrainageSourceUnavailable("CHANGCHUN_DRAINAGE_ENDPOINT is not configured")
        try:
            body, content_type = self._request(latitude, longitude)
            rows = self._parse(body, content_type)
            batch = self._normalise(rows, source="changchun-configured", is_live=True, depth_unit=self.config.depth_unit)
            self._save_cache(batch)
            return batch
        except Exception as exc:
            if allow_cache:
                cached = self._load_cache()
                if cached is not None:
                    return DrainageObservationBatch(
                        observations=cached.observations,
                        source="changchun-drainage-cache",
                        is_live=False,
                        retrieved_at=cached.retrieved_at,
                        provenance={
                            **cached.provenance,
                            "fallback_reason": f"{type(exc).__name__}: {exc}",
                            "label_quality": "cached",
                        },
                    )
            if isinstance(exc, DrainageDataError):
                raise
            raise DrainageSourceUnavailable(f"Changchun drainage request failed: {exc}") from exc

    def _request(self, latitude: float | None, longitude: float | None) -> tuple[bytes, str]:
        endpoint = self.config.endpoint
        query = {}
        if latitude is not None:
            query["latitude"] = f"{float(latitude):.5f}"
        if longitude is not None:
            query["longitude"] = f"{float(longitude):.5f}"
        if query:
            endpoint = endpoint + ("&" if "?" in endpoint else "?") + urllib.parse.urlencode(query)
        headers = {"Accept": "application/json, text/csv, application/geo+json, */*", "User-Agent": "tianheng-weather-impact/0.3"}
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        request = urllib.request.Request(endpoint, headers=headers)
        if endpoint.startswith("file://"):
            body = Path(urllib.parse.urlparse(endpoint).path).read_bytes()
            return body, ""
        with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
            return response.read(), str(response.headers.get("Content-Type", ""))

    @staticmethod
    def _parse(body: bytes, content_type: str) -> list[Mapping[str, Any]]:
        text = body.decode("utf-8-sig")
        if "csv" in content_type.lower() or (text.strip() and text.lstrip()[0] not in "[{"):
            return list(csv.DictReader(io.StringIO(text)))
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DrainageDataError(f"drainage response is not JSON/CSV: {exc}") from exc
        if isinstance(payload, Mapping):
            if payload.get("type") == "FeatureCollection":
                rows = []
                for feature in payload.get("features", []):
                    properties = dict(feature.get("properties") or {})
                    coords = (feature.get("geometry") or {}).get("coordinates") or []
                    if len(coords) >= 2:
                        properties.setdefault("longitude", coords[0])
                        properties.setdefault("latitude", coords[1])
                    rows.append(properties)
                return rows
            for key in ("data", "result", "rows", "records", "observations"):
                if isinstance(payload.get(key), list):
                    return [item for item in payload[key] if isinstance(item, Mapping)]
            return [payload]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, Mapping)]
        raise DrainageDataError("drainage payload has no observation rows")

    @classmethod
    def _normalise(cls, rows: Iterable[Mapping[str, Any]], source: str, is_live: bool, depth_unit: str = "cm") -> DrainageObservationBatch:
        observations: list[DrainageObservation] = []
        for index, row in enumerate(rows):
            lat = _float(_first(row, "latitude", "lat", "纬度", "y"), float("nan"))
            lon = _float(_first(row, "longitude", "lon", "lng", "经度", "x"), float("nan"))
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            depth_mm_raw = _first(row, "water_depth_mm", "depth_mm", "water_level_mm", "积水深度毫米", default=None)
            if depth_mm_raw is not None:
                depth = _float(depth_mm_raw, 0.0)
            else:
                depth_raw = _float(_first(row, "water_depth_cm", "depth_cm", "积水深度", "water_level", "水深"), 0.0)
                unit = str(depth_unit).lower()
                depth = depth_raw * (1000.0 if unit in ("m", "meter", "meters", "米") else 1.0 if unit in ("mm", "毫米") else 10.0)
            observed_at = str(_first(row, "observed_at", "timestamp", "time", "时间", default=_utc_now()))
            observation_id = str(_first(row, "observation_id", "id", "station_id", "point_id", "点位编号", default=f"drainage_{index:04d}"))
            rainfall = _first(row, "rainfall_mm", "rain_mm", "降雨量", default=None)
            observations.append(
                DrainageObservation(
                    observation_id=observation_id,
                    observed_at=observed_at,
                    latitude=lat,
                    longitude=lon,
                    water_depth_mm=max(0.0, depth),
                    status=str(_first(row, "status", "state", "状态", default="unknown")),
                    rainfall_mm=None if rainfall is None else max(0.0, _float(rainfall)),
                    source=source,
                    is_live=is_live,
                    raw=dict(row),
                )
            )
        if not observations:
            raise DrainageDataError("no valid drainage observations after field validation")
        return DrainageObservationBatch(
            observations=tuple(observations),
            source=source,
            is_live=is_live,
            retrieved_at=_utc_now(),
            provenance={"label_quality": "real" if is_live else "cached", "count": len(observations)},
        )

    def _save_cache(self, batch: DrainageObservationBatch) -> None:
        (self.cache_dir / "latest.json").write_text(json.dumps(batch.to_dict(), ensure_ascii=False), encoding="utf-8")

    def _load_cache(self) -> DrainageObservationBatch | None:
        path = self.cache_dir / "latest.json"
        if not path.exists():
            return None
        age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
        if age > max(0, self.config.max_cache_age_seconds):
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("observations", [])
            observations = tuple(
                DrainageObservation(
                    observation_id=str(row["observation_id"]),
                    observed_at=str(row["observed_at"]),
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    water_depth_mm=float(row.get("water_depth_mm", 0.0)),
                    status=str(row.get("status", "unknown")),
                    rainfall_mm=row.get("rainfall_mm"),
                    source="changchun-drainage-cache",
                    is_live=False,
                    raw=dict(row.get("raw", {})),
                )
                for row in rows
            )
            if not observations:
                return None
            return DrainageObservationBatch(
                observations=observations,
                source="changchun-drainage-cache",
                is_live=False,
                retrieved_at=str(payload.get("retrieved_at", _utc_now())),
                provenance={**dict(payload.get("provenance", {})), "cache_age_seconds": round(age, 2)},
            )
        except Exception:
            return None


__all__ = [
    "ChangchunDrainageAdapter",
    "ChangchunDrainageConfig",
    "DrainageObservation",
    "DrainageObservationBatch",
    "DrainageDataError",
    "DrainageSourceUnavailable",
]
