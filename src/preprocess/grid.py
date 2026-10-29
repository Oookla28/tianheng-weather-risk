"""网格构建与地形派生特征（DEM → 坡度 / 汇流 / 洼地 / 距水系）。

这是"跨分辨率融合"的物理侧输入：气象数据约 10km 尺度，而地形与设施数据可以更细。
本模块不依赖 GDAL/rasterio，用 numpy 在规则网格上实现 D8 汇流与洼地指数，
保证在离线、无 GIS 依赖的环境里也能复现。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd

# D8 邻域偏移（顺时针）
_D8 = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]


@dataclass
class TerrainField:
    """二维地形场及其派生量。"""

    elevation: np.ndarray
    slope: np.ndarray
    flow_accumulation: np.ndarray
    depression_index: np.ndarray
    sink_depth: np.ndarray
    water_mask: np.ndarray

    def stack(self) -> Dict[str, np.ndarray]:
        return {
            "elevation": self.elevation,
            "slope": self.slope,
            "flow_accumulation": self.flow_accumulation,
            "depression_index": self.depression_index,
            "sink_depth": self.sink_depth,
        }


def _smooth(field: np.ndarray, passes: int = 1) -> np.ndarray:
    out = field.astype(float)
    for _ in range(passes):
        padded = np.pad(out, 1, mode="edge")
        acc = np.zeros_like(out)
        for dy, dx in _D8:
            acc += padded[1 + dy : 1 + dy + out.shape[0], 1 + dx : 1 + dx + out.shape[1]]
        out = acc / len(_D8)
    return out


def make_elevation(n_rows: int, n_cols: int, rng: np.random.Generator) -> np.ndarray:
    """构造一条自西北向东南的浅谷地，并叠加低频起伏与高频噪声。"""
    yy, xx = np.mgrid[0:n_rows, 0:n_cols]
    # 整体坡向：北高南低、西高东低
    base = 96.0 + 1.05 * (n_rows - yy) + 0.55 * xx
    # 主谷地（汇流走廊）
    valley_x = n_cols * 0.52 + 1.8 * np.sin(yy / max(1, n_rows) * np.pi)
    valley = 21.0 * np.exp(-((xx - valley_x) ** 2) / 26.0)
    # 次级洼地
    pond = 9.0 * np.exp(-(((xx - n_cols * 0.22) ** 2 + (yy - n_rows * 0.72) ** 2)) / 18.0)
    pond += 7.0 * np.exp(-(((xx - n_cols * 0.78) ** 2 + (yy - n_rows * 0.35) ** 2)) / 14.0)
    ridge = 6.0 * np.exp(-(((xx - n_cols * 0.85) ** 2 + (yy - n_rows * 0.88) ** 2)) / 40.0)
    fine = _smooth(rng.normal(0, 1.6, size=(n_rows, n_cols)), passes=1)
    return base - valley - pond + ridge + fine


def compute_slope(elevation: np.ndarray, cell_size_m: float) -> np.ndarray:
    gy, gx = np.gradient(elevation, cell_size_m, cell_size_m)
    return np.hypot(gx, gy)


def compute_flow_accumulation(elevation: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """D8 最陡下降汇流累积，返回（汇流累积面积, 汇流方向索引）。"""
    n_rows, n_cols = elevation.shape
    direction = np.full((n_rows, n_cols), -1, dtype=int)
    steepest = np.zeros((n_rows, n_cols), dtype=float)
    for iy in range(n_rows):
        for ix in range(n_cols):
            best = 0.0
            best_dir = -1
            for k, (dy, dx) in enumerate(_D8):
                jy, jx = iy + dy, ix + dx
                if 0 <= jy < n_rows and 0 <= jx < n_cols:
                    drop = (elevation[iy, ix] - elevation[jy, jx]) / (1.4142 if dy and dx else 1.0)
                    if drop > best:
                        best = drop
                        best_dir = k
            steepest[iy, ix] = best
            direction[iy, ix] = best_dir

    accumulation = np.ones((n_rows, n_cols), dtype=float)
    order = np.argsort(-elevation, axis=None)  # 高→低，天然拓扑序
    flat_elev = elevation.ravel()
    for idx in order:
        iy, ix = divmod(int(idx), n_cols)
        k = direction[iy, ix]
        if k < 0:
            continue
        dy, dx = _D8[k]
        jy, jx = iy + dy, ix + dx
        if 0 <= jy < n_rows and 0 <= jx < n_cols:
            accumulation[jy, jx] += accumulation[iy, ix]
    assert flat_elev.size == accumulation.size
    return accumulation, direction


def compute_depression(elevation: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """局部洼地深度与真洼地（无下游）深度。"""
    n_rows, n_cols = elevation.shape
    padded = np.pad(elevation, 1, mode="edge")
    neighbor_min = np.full((n_rows, n_cols), np.inf)
    for dy, dx in _D8:
        neighbor_min = np.minimum(neighbor_min, padded[1 + dy : 1 + dy + n_rows, 1 + dx : 1 + dx + n_cols])
    depression = np.clip(neighbor_min - elevation, 0, None)
    _, direction = compute_flow_accumulation(elevation)
    sink = (direction < 0).astype(float)
    sink_depth = depression * (1.0 + 2.0 * sink)
    return depression, sink_depth


def build_terrain(n_rows: int, n_cols: int, cell_size_m: float, seed: int = 42) -> TerrainField:
    rng = np.random.default_rng(seed)
    elevation = make_elevation(n_rows, n_cols, rng)
    slope = compute_slope(elevation, cell_size_m)
    accumulation, _ = compute_flow_accumulation(elevation)
    depression, sink_depth = compute_depression(elevation)
    threshold = np.quantile(accumulation, 0.94)
    water_mask = (accumulation >= threshold).astype(float)
    return TerrainField(
        elevation=elevation,
        slope=slope,
        flow_accumulation=accumulation,
        depression_index=depression,
        sink_depth=sink_depth,
        water_mask=water_mask,
    )


def _normalize(values: np.ndarray) -> np.ndarray:
    lo, hi = float(values.min()), float(values.max())
    return (values - lo) / (hi - lo + 1e-9)


def distance_to_water(water_mask: np.ndarray) -> np.ndarray:
    n_rows, n_cols = water_mask.shape
    water_cells = np.argwhere(water_mask > 0)
    out = np.full((n_rows, n_cols), np.inf)
    if len(water_cells) == 0:
        return np.zeros((n_rows, n_cols))
    for iy in range(n_rows):
        for ix in range(n_cols):
            d = np.hypot(water_cells[:, 0] - iy, water_cells[:, 1] - ix)
            out[iy, ix] = float(d.min())
    return out


def build_grid_frame(
    n_rows: int,
    n_cols: int,
    cell_size_m: float,
    origin_lon: float,
    origin_lat: float,
    seed: int = 42,
) -> pd.DataFrame:
    """构建网格表：静态地形 + 土地覆盖 + 易涝度。"""
    terrain = build_terrain(n_rows, n_cols, cell_size_m, seed=seed)
    rng = np.random.default_rng(seed + 17)

    yy, xx = np.mgrid[0:n_rows, 0:n_cols]
    dist_water = distance_to_water(terrain.water_mask)
    # 土地覆盖：中心城区不透水面高，边缘为绿地/农田
    urban_core = np.exp(-(((xx - n_cols * 0.5) ** 2 + (yy - n_rows * 0.45) ** 2)) / 45.0)
    impervious = np.clip(0.18 + 0.62 * urban_core + rng.normal(0, 0.05, size=(n_rows, n_cols)), 0.03, 0.97)
    green_ratio = np.clip(1.0 - impervious - rng.normal(0, 0.04, size=(n_rows, n_cols)), 0.02, 0.95)

    # 易涝度：汇流、低洼、坡度倒数与不透水面共同决定（透明可解释）
    flow_n = _normalize(np.log1p(terrain.flow_accumulation))
    dep_n = _normalize(terrain.depression_index)
    low_n = 1.0 - _normalize(_smooth(terrain.elevation, passes=2))
    flat_n = 1.0 - _normalize(terrain.slope)
    susceptibility = (
        0.34 * flow_n
        + 0.26 * dep_n
        + 0.18 * low_n
        + 0.10 * flat_n
        + 0.12 * impervious
    )
    susceptibility = _normalize(susceptibility)

    rows = []
    for iy in range(n_rows):
        for ix in range(n_cols):
            rows.append(
                {
                    "cell_id": f"c_{iy:02d}_{ix:02d}",
                    "x": ix,
                    "y": iy,
                    "lon": round(origin_lon + ix * cell_size_m / 111_320.0, 6),
                    "lat": round(origin_lat + iy * cell_size_m / 110_540.0, 6),
                    "elevation": float(terrain.elevation[iy, ix]),
                    "slope": float(terrain.slope[iy, ix]),
                    "flow_accumulation": float(terrain.flow_accumulation[iy, ix]),
                    "depression_index": float(terrain.depression_index[iy, ix]),
                    "sink_depth": float(terrain.sink_depth[iy, ix]),
                    "dist_to_water": float(dist_water[iy, ix]),
                    "impervious_ratio": float(impervious[iy, ix]),
                    "green_ratio": float(green_ratio[iy, ix]),
                    "urban_intensity": float(urban_core[iy, ix]),
                    "susceptibility": float(susceptibility[iy, ix]),
                    "is_water": int(terrain.water_mask[iy, ix] > 0),
                }
            )
    frame = pd.DataFrame(rows)
    frame["susceptibility_rank"] = frame["susceptibility"].rank(pct=True)
    return frame


__all__ = [
    "TerrainField",
    "build_terrain",
    "build_grid_frame",
    "make_elevation",
    "compute_slope",
    "compute_flow_accumulation",
    "compute_depression",
    "distance_to_water",
]
