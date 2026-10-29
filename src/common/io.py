"""统一 IO：优先 Parquet，缺失 pyarrow 时自动退回 CSV，保证离线可跑。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import pandas as pd


def _parquet_available() -> bool:
    try:
        import pyarrow  # noqa: F401

        return True
    except Exception:
        return False


def write_table(frame: pd.DataFrame, path: str | Path, also_csv: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    use_parquet = path.suffix == ".parquet" and _parquet_available()
    if use_parquet:
        frame.to_parquet(path, index=False)
    else:
        path = path.with_suffix(".csv")
        frame.to_csv(path, index=False, encoding="utf-8-sig")
    if also_csv and use_parquet:
        frame.to_csv(path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    return path


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.exists() and path.suffix == ".parquet" and _parquet_available():
        return pd.read_parquet(path)
    fallback = path.with_suffix(".csv")
    if fallback.exists():
        return pd.read_csv(fallback)
    if path.exists():
        return pd.read_csv(path)
    raise FileNotFoundError(f"未找到数据表：{path}")


def save_frames(frames: Mapping[str, pd.DataFrame], directory: str | Path) -> Dict[str, str]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: Dict[str, str] = {}
    for name, frame in frames.items():
        written[name] = str(write_table(frame, directory / f"{name}.parquet"))
    return written


def load_frames(names: list[str], directory: str | Path) -> Dict[str, pd.DataFrame]:
    directory = Path(directory)
    return {name: read_table(directory / f"{name}.parquet") for name in names}


def write_json(payload: Any, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def read_json(path: str | Path, default: Optional[Any] = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(text: str, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def table_exists(directory: str | Path, name: str) -> bool:
    directory = Path(directory)
    return (directory / f"{name}.parquet").exists() or (directory / f"{name}.csv").exists()
