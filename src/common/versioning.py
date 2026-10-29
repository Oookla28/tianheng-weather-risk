"""版本戳与可复现性工具。

数据版本 = 关键表内容的哈希；模型版本 = 配置 + 特征列 + 训练集标记的哈希。
这样"同版本"在答辩现场可以被验证，而不是一句口头承诺。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


def _canonical(obj: Any) -> str:
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    if isinstance(obj, Mapping):
        return "{" + ",".join(f"{k}:{_canonical(v)}" for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))) + "}"
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(_canonical(v) for v in obj) + "]"
    return json.dumps(str(obj), ensure_ascii=False)


def stable_hash(obj: Any, length: int = 12) -> str:
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()[:length]


def dataframe_fingerprint(frame: pd.DataFrame, columns: Sequence[str] | None = None) -> str:
    """对 DataFrame 的关键列做稳定指纹，不受行序影响。"""
    if frame is None or len(frame) == 0:
        return "empty"
    use = list(columns) if columns else list(frame.columns)
    use = [c for c in use if c in frame.columns]
    sub = frame[use].copy()
    for col in sub.columns:
        sub[col] = sub[col].astype(str)
    sub = sub.sort_values(by=use).reset_index(drop=True)
    digest = hashlib.sha256()
    digest.update("|".join(use).encode("utf-8"))
    digest.update(pd.util.hash_pandas_object(sub, index=False).to_numpy(dtype=np.uint64).tobytes())
    return digest.hexdigest()[:12]


def file_sha256(path: str | Path, length: int = 12) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:length]


def data_version(parts: Iterable[tuple[str, str]]) -> str:
    """把多张表的指纹合成一个数据版本号，例如 ``demo-v1-3f9c2a``。"""
    payload = sorted(parts)
    return "dv-" + stable_hash(payload, 10) if payload else "dv-empty"


def model_version(name: str, config: Mapping[str, Any], feature_cols: Sequence[str], extra: Mapping[str, Any] | None = None) -> str:
    payload = {
        "name": name,
        "config": dict(config),
        "features": list(feature_cols),
        "extra": dict(extra or {}),
    }
    return f"{name}@{stable_hash(payload, 8)}"


def write_version_stamp(path: str | Path, payload: Mapping[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path
