"""Authorised CMA radar volume adapter with cache and quality checks.

CMA radar products are distributed through authenticated services whose URL and
credentials vary by account and product.  This adapter keeps that boundary
configurable instead of embedding a guessed endpoint.  It accepts a JSON
payload containing ``values``/``reflectivity`` or a URL to a ``.npy``/``.npz``
product and normalises it to :class:`RadarVoxelCube`.

Set ``CMA_RADAR_ENDPOINT`` and, when required, ``CMA_RADAR_TOKEN`` in the
runtime environment.  When a live request fails, an age-limited cached product
may be returned with ``is_live=False`` and provenance set to ``cached``.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ..radar.voxel import RadarVoxelCube


class RadarDataError(RuntimeError):
    """Raised when a radar response cannot be validated."""


class RadarSourceUnavailable(RuntimeError):
    """Raised when no live or usable cached radar product is available."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


@dataclass(frozen=True)
class CmaRadarConfig:
    endpoint: str = field(default_factory=lambda: os.getenv("CMA_RADAR_ENDPOINT", ""))
    token: str = field(default_factory=lambda: os.getenv("CMA_RADAR_TOKEN", ""))
    product: str = field(default_factory=lambda: os.getenv("CMA_RADAR_PRODUCT", "reflectivity"))
    # Optional official data-service parameters.  The account-specific
    # endpoint may expose getRadaFileByTimeRange or a product download URL.
    data_code: str = field(default_factory=lambda: os.getenv("CMA_RADAR_DATA_CODE", ""))
    time_range: str = field(default_factory=lambda: os.getenv("CMA_RADAR_TIME_RANGE", ""))
    station_ids: str = field(default_factory=lambda: os.getenv("CMA_RADAR_STATION_IDS", ""))
    timeout_seconds: float = field(default_factory=lambda: float(os.getenv("CMA_RADAR_TIMEOUT", "8")))
    cache_dir: str = field(default_factory=lambda: os.getenv("CMA_RADAR_CACHE_DIR", "data/cache/cma_radar"))
    max_cache_age_seconds: int = field(default_factory=lambda: int(os.getenv("CMA_RADAR_MAX_CACHE_AGE", "1800")))


@dataclass(frozen=True)
class RadarFetchResult:
    cube: RadarVoxelCube
    source: str
    is_live: bool
    retrieved_at: str
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "is_live": self.is_live,
            "retrieved_at": self.retrieved_at,
            "provenance": dict(self.provenance),
            "cube": self.cube.to_dict(include_values=False),
        }


class CmaRadarAdapter:
    """Fetch and normalise an authorised CMA radar volume.

    The adapter is intentionally transport-agnostic.  A CMA product gateway
    can return JSON directly, a JSON envelope containing a download URL, or a
    NumPy ``.npy``/``.npz`` file.  All three forms are converted to the same
    four-dimensional cube contract used by the nowcast module.
    """

    def __init__(self, config: CmaRadarConfig | None = None) -> None:
        self.config = config or CmaRadarConfig()
        self.cache_dir = Path(self.config.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_latest(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        *,
        allow_cache: bool = True,
    ) -> RadarFetchResult:
        if not self.config.endpoint:
            if allow_cache:
                cached = self._load_cache()
                if cached is not None:
                    return cached
            raise RadarSourceUnavailable("CMA_RADAR_ENDPOINT is not configured")

        try:
            payload, content_type = self._request(latitude, longitude)
            cube, source_meta = self._normalise(payload, content_type, latitude, longitude)
            result = RadarFetchResult(
                cube=cube,
                source="cma-authorised",
                is_live=True,
                retrieved_at=_utc_now(),
                provenance={
                    "endpoint": self._safe_endpoint(self.config.endpoint),
                    "product": self.config.product,
                    "label_quality": "real",
                    **source_meta,
                },
            )
            self._save_cache(result)
            return result
        except Exception as exc:
            if allow_cache:
                cached = self._load_cache()
                if cached is not None:
                    return RadarFetchResult(
                        cube=cached.cube,
                        source="cma-cache",
                        is_live=False,
                        retrieved_at=cached.retrieved_at,
                        provenance={
                            **cached.provenance,
                            "fallback_reason": f"{type(exc).__name__}: {exc}",
                            "label_quality": "cached",
                        },
                    )
            if isinstance(exc, RadarDataError):
                raise
            raise RadarSourceUnavailable(f"CMA radar request failed: {exc}") from exc

    def _request(self, latitude: float | None, longitude: float | None) -> tuple[Any, str]:
        endpoint = self.config.endpoint
        query: dict[str, str] = {}
        if self.config.data_code:
            query["dataCode"] = self.config.data_code
        elif self.config.product:
            query["product"] = self.config.product
        if self.config.time_range:
            query["timeRange"] = self.config.time_range
        if self.config.station_ids:
            query["staIds"] = self.config.station_ids
        if self.config.data_code:
            query.setdefault("dataFormat", "json")
        if latitude is not None:
            query["latitude"] = f"{float(latitude):.5f}"
        if longitude is not None:
            query["longitude"] = f"{float(longitude):.5f}"
        if query:
            endpoint = endpoint + ("&" if "?" in endpoint else "?") + urllib.parse.urlencode(query)
        headers = {"Accept": "application/json, application/octet-stream, */*", "User-Agent": "tianheng-weather-impact/0.3"}
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        request = urllib.request.Request(endpoint, headers=headers)
        if endpoint.startswith("file://"):
            path = Path(urllib.parse.urlparse(endpoint).path)
            body = path.read_bytes()
            content_type = "application/octet-stream"
        else:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = response.read()
                content_type = str(response.headers.get("Content-Type", ""))
        if "json" in content_type.lower() or body.lstrip()[:1] in (b"{", b"["):
            return json.loads(body.decode("utf-8")), content_type
        return body, content_type

    def _normalise(
        self,
        payload: Any,
        content_type: str,
        latitude: float | None,
        longitude: float | None,
    ) -> tuple[RadarVoxelCube, dict[str, Any]]:
        metadata: dict[str, Any] = {}
        if isinstance(payload, (bytes, bytearray)):
            values, metadata = self._read_numpy_bytes(bytes(payload))
        elif isinstance(payload, list):
            values = np.asarray(payload)
        elif isinstance(payload, Mapping):
            values, metadata = self._extract_mapping(payload)
        else:
            raise RadarDataError(f"unsupported CMA response type: {type(payload).__name__}")

        values = np.asarray(values, dtype=np.float32)
        if values.ndim == 2:
            values = values[None, None, :, :]
        elif values.ndim == 3:
            values = values[None, :, :, :]
        if values.ndim != 4:
            raise RadarDataError(f"radar reflectivity must be 2-D, 3-D or 4-D; got {values.shape}")
        if values.size == 0 or not np.isfinite(values).any():
            raise RadarDataError("radar reflectivity is empty or non-finite")
        values = np.nan_to_num(values, nan=0.0, posinf=100.0, neginf=0.0)
        values = np.clip(values, 0.0, 100.0)
        times = _first(metadata, "timestamps", "times", "timestamp", default=None)
        if isinstance(times, str):
            times = [times]
        times = list(times or [])
        if len(times) != values.shape[0]:
            times = [_utc_now() for _ in range(values.shape[0])]
        heights = np.asarray(_first(metadata, "heights_m", "heights", "altitudes_m", default=[]), dtype=np.float32)
        if heights.size != values.shape[1]:
            heights = np.arange(values.shape[1], dtype=np.float32) * 1000.0 + 500.0
        origin_lat = _as_float(_first(metadata, "origin_lat", "latitude", default=latitude), 43.88)
        origin_lon = _as_float(_first(metadata, "origin_lon", "longitude", default=longitude), 125.32)
        cell_size_m = _as_float(_first(metadata, "cell_size_m", "resolution_m", default=1000.0), 1000.0)
        cube = RadarVoxelCube(
            values=values,
            timestamps=[str(item) for item in times],
            heights_m=heights,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            cell_size_m=max(cell_size_m, 1.0),
            source="cma-authorised",
        )
        return cube, {"shape": list(cube.shape), "content_type": content_type or "unknown"}

    def _extract_mapping(self, payload: Mapping[str, Any]) -> tuple[Any, dict[str, Any]]:
        # Product gateways often wrap the actual data in data/result/payload.
        for key in ("data", "result", "payload"):
            child = payload.get(key)
            if isinstance(child, Mapping):
                try:
                    return self._extract_mapping(child)
                except RadarDataError:
                    pass
            if isinstance(child, list):
                return child, dict(payload)
        # CMA file-information responses commonly use DS/fileInfos and upper
        # case FILE_URL fields; normalize those envelopes before reading data.
        for key in ("DS", "ds", "files", "fileInfos", "file_infos", "items"):
            items = payload.get(key)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, Mapping):
                        try:
                            return self._extract_mapping(item)
                        except RadarDataError:
                            continue
        for key in ("download_url", "downloadUrl", "url", "file_url", "FILE_URL", "FILE_PATH"):
            url = payload.get(key)
            if isinstance(url, str) and url:
                url = urllib.parse.urljoin(self.config.endpoint, url)
                body, content_type = self._request_url(url)
                if isinstance(body, Mapping):
                    return self._extract_mapping(body)
                if isinstance(body, list):
                    return body, {}
                if "json" in content_type.lower() or body.lstrip()[:1] in (b"{", b"["):
                    decoded = json.loads(bytes(body).decode("utf-8"))
                    if isinstance(decoded, Mapping):
                        return self._extract_mapping(decoded)
                    return decoded, {}
                return self._read_numpy_bytes(bytes(body))
        for key in ("values", "reflectivity", "radar", "dbz", "array"):
            if key in payload:
                return payload[key], dict(payload)
        raise RadarDataError("CMA payload has no values/reflectivity field")

    def _request_url(self, url: str) -> tuple[Any, str]:
        headers = {"User-Agent": "tianheng-weather-impact/0.3"}
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        request = urllib.request.Request(url, headers=headers)
        if url.startswith("file://"):
            body = Path(urllib.parse.urlparse(url).path).read_bytes()
            content_type = "application/octet-stream"
        else:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = response.read()
                content_type = str(response.headers.get("Content-Type", ""))
        if "json" in content_type.lower() or body.lstrip()[:1] in (b"{", b"["):
            return json.loads(body.decode("utf-8")), content_type
        return body, content_type

    @staticmethod
    def _read_numpy_bytes(body: bytes) -> tuple[np.ndarray, dict[str, Any]]:
        import io

        try:
            loaded = np.load(io.BytesIO(body), allow_pickle=False)
        except Exception as exc:
            raise RadarDataError(f"binary radar product is not NumPy npy/npz: {exc}") from exc
        if isinstance(loaded, np.ndarray):
            return loaded, {}
        keys = list(loaded.files)
        if not keys:
            raise RadarDataError("npz radar product is empty")
        value_key = next((k for k in ("values", "reflectivity", "dbz", "array") if k in keys), keys[0])
        metadata: dict[str, Any] = {}
        for key in ("timestamps", "heights_m", "origin_lat", "origin_lon", "cell_size_m"):
            if key in keys:
                item = loaded[key]
                metadata[key] = item.tolist() if hasattr(item, "tolist") else item
        return loaded[value_key], metadata

    def _save_cache(self, result: RadarFetchResult) -> None:
        np.savez_compressed(
            self.cache_dir / "latest.npz",
            values=result.cube.values,
            timestamps=np.asarray(result.cube.timestamps, dtype="U64"),
            heights_m=result.cube.heights_m,
            origin_lat=result.cube.origin_lat,
            origin_lon=result.cube.origin_lon,
            cell_size_m=result.cube.cell_size_m,
        )
        (self.cache_dir / "latest.json").write_text(json.dumps(result.to_dict(), ensure_ascii=False), encoding="utf-8")

    def _load_cache(self) -> RadarFetchResult | None:
        metadata_path = self.cache_dir / "latest.json"
        array_path = self.cache_dir / "latest.npz"
        if not metadata_path.exists() or not array_path.exists():
            return None
        age = datetime.now(timezone.utc).timestamp() - metadata_path.stat().st_mtime
        if age > max(0, self.config.max_cache_age_seconds):
            return None
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            with np.load(array_path, allow_pickle=False) as loaded:
                cube = RadarVoxelCube(
                    values=loaded["values"],
                    timestamps=[str(x) for x in loaded["timestamps"].tolist()],
                    heights_m=loaded["heights_m"],
                    origin_lat=float(loaded["origin_lat"]),
                    origin_lon=float(loaded["origin_lon"]),
                    cell_size_m=float(loaded["cell_size_m"]),
                    source="cma-cache",
                )
            return RadarFetchResult(
                cube=cube,
                source="cma-cache",
                is_live=False,
                retrieved_at=str(payload.get("retrieved_at", _utc_now())),
                provenance={**dict(payload.get("provenance", {})), "cache_age_seconds": round(age, 2)},
            )
        except Exception:
            return None

    @staticmethod
    def _safe_endpoint(endpoint: str) -> str:
        parsed = urllib.parse.urlsplit(endpoint)
        if not parsed.scheme:
            return "configured"
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


__all__ = ["CmaRadarAdapter", "CmaRadarConfig", "RadarFetchResult", "RadarDataError", "RadarSourceUnavailable"]
