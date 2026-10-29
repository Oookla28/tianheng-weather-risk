"""可复现的雷达体素场与轻量短临外推。

The representation is ``(time, height, y, x)`` and accepts either authorised
radar volumes or the deterministic generator used by tests and demos.  The
advection baseline intentionally stays dependency-light; a trained model can
replace ``nowcast`` while preserving the same cube contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np


@dataclass(frozen=True)
class VoxelSummary:
    timestamp: str
    max_reflectivity: float
    mean_reflectivity: float
    convective_fraction: float
    core_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "max_reflectivity": self.max_reflectivity,
            "mean_reflectivity": self.mean_reflectivity,
            "convective_fraction": self.convective_fraction,
            "core_count": self.core_count,
        }


@dataclass
class RadarVoxelCube:
    values: np.ndarray
    timestamps: list[str]
    heights_m: np.ndarray
    origin_lat: float
    origin_lon: float
    cell_size_m: float = 1000.0
    source: str = "synthetic"

    def __post_init__(self) -> None:
        self.values = np.asarray(self.values, dtype=np.float32)
        self.heights_m = np.asarray(self.heights_m, dtype=np.float32)
        if self.values.ndim != 4:
            raise ValueError("values must have shape (time, height, y, x)")
        if self.values.shape[0] != len(self.timestamps):
            raise ValueError("timestamps length must equal time dimension")
        if self.values.shape[1] != len(self.heights_m):
            raise ValueError("heights length must equal height dimension")
        if self.cell_size_m <= 0:
            raise ValueError("cell_size_m must be positive")

    @classmethod
    def synthetic(
        cls,
        n_times: int = 8,
        n_heights: int = 4,
        n_rows: int = 32,
        n_cols: int = 32,
        seed: int = 42,
        origin_lat: float = 43.88,
        origin_lon: float = 125.32,
    ) -> "RadarVoxelCube":
        rng = np.random.default_rng(seed)
        yy, xx = np.mgrid[0:n_rows, 0:n_cols]
        values = np.zeros((n_times, n_heights, n_rows, n_cols), dtype=np.float32)
        for t in range(n_times):
            cx = n_cols * 0.25 + 1.1 * t
            cy = n_rows * 0.62 - 0.55 * t
            radius = 3.5 + 0.14 * t
            core = 58.0 * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * radius**2))
            secondary = 33.0 * np.exp(-((xx - n_cols * 0.72) ** 2 + (yy - n_rows * 0.35 + 0.3 * t) ** 2) / 40.0)
            for h in range(n_heights):
                decay = np.exp(-0.18 * h)
                noise = rng.normal(0, 1.2, size=(n_rows, n_cols))
                values[t, h] = np.clip((core + secondary) * decay + noise, 0.0, 75.0)
        start = datetime.now(timezone.utc).replace(microsecond=0)
        timestamps = [(start + timedelta(minutes=5 * i)).isoformat().replace("+00:00", "Z") for i in range(n_times)]
        heights = np.arange(n_heights, dtype=np.float32) * 1000.0 + 500.0
        return cls(values, timestamps, heights, origin_lat, origin_lon, source="synthetic-radar")

    @property
    def shape(self) -> tuple[int, int, int, int]:
        return tuple(int(x) for x in self.values.shape)

    def summary(self, threshold_dbz: float = 40.0) -> list[VoxelSummary]:
        summaries: list[VoxelSummary] = []
        for idx, frame in enumerate(self.values):
            max_reflectivity = float(frame.max(initial=0.0))
            convective = frame >= float(threshold_dbz)
            core_count = int(_connected_components(convective.max(axis=0)))
            summaries.append(
                VoxelSummary(
                    timestamp=self.timestamps[idx],
                    max_reflectivity=round(max_reflectivity, 3),
                    mean_reflectivity=round(float(frame.mean()), 3),
                    convective_fraction=round(float(convective.mean()), 5),
                    core_count=core_count,
                )
            )
        return summaries

    def convective_score(self, threshold_dbz: float = 40.0) -> float:
        latest = self.values[-1]
        return float(np.clip(latest.max() / 65.0 * 0.55 + (latest >= threshold_dbz).mean() * 0.45, 0.0, 1.0))

    def nowcast(self, horizons: int = 3, shift_y: float = -0.55, shift_x: float = 1.1) -> "RadarVoxelCube":
        """Advect the latest volume with bilinear-free integer translation."""

        if horizons < 1:
            raise ValueError("horizons must be >= 1")
        latest = self.values[-1]
        frames = []
        for step in range(1, horizons + 1):
            frame = np.zeros_like(latest)
            dy, dx = int(round(shift_y * step)), int(round(shift_x * step))
            source_y0, source_y1 = max(0, -dy), min(latest.shape[-2], latest.shape[-2] - dy)
            source_x0, source_x1 = max(0, -dx), min(latest.shape[-1], latest.shape[-1] - dx)
            dest_y0, dest_y1 = max(0, dy), min(latest.shape[-2], latest.shape[-2] + dy)
            dest_x0, dest_x1 = max(0, dx), min(latest.shape[-1], latest.shape[-1] + dx)
            if source_y1 > source_y0 and source_x1 > source_x0:
                frame[:, dest_y0:dest_y1, dest_x0:dest_x1] = latest[:, source_y0:source_y1, source_x0:source_x1]
            frames.append(frame)
        last_time = _parse_time(self.timestamps[-1])
        timestamps = [(last_time + timedelta(minutes=5 * i)).isoformat().replace("+00:00", "Z") for i in range(1, horizons + 1)]
        return RadarVoxelCube(np.stack(frames), timestamps, self.heights_m.copy(), self.origin_lat, self.origin_lon, self.cell_size_m, source="advection-nowcast")

    def to_dict(self, include_values: bool = False) -> dict[str, Any]:
        result = {
            "shape": list(self.shape),
            "timestamps": self.timestamps,
            "heights_m": self.heights_m.tolist(),
            "origin": {"latitude": self.origin_lat, "longitude": self.origin_lon},
            "cell_size_m": self.cell_size_m,
            "source": self.source,
            "summary": [item.to_dict() for item in self.summary()],
            "convective_score": self.convective_score(),
        }
        if include_values:
            result["values"] = self.values.tolist()
        return result


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _connected_components(mask: np.ndarray) -> int:
    """Count 4-connected components without scipy/skimage."""

    mask = np.asarray(mask, dtype=bool)
    seen = np.zeros(mask.shape, dtype=bool)
    count = 0
    rows, cols = mask.shape
    for y, x in zip(*np.where(mask)):
        if seen[y, x]:
            continue
        count += 1
        stack = [(int(y), int(x))]
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < rows and 0 <= nx < cols and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
    return count


__all__ = ["RadarVoxelCube", "VoxelSummary"]
