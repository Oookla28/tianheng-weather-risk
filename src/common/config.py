"""配置加载、路径解析与全局常量。

所有阈值、资源上限与实验设置都从 ``configs/*.yaml`` 读取，避免把口径写死在代码里。
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from .. import ARTIFACT_DIR, CONFIG_DIR, DATA_DIR, PROJECT_ROOT

# ---------------------------------------------------------------- YAML 加载

try:  # pragma: no cover - 依赖是否安装由环境决定
    import yaml as _yaml
except Exception:  # pragma: no cover
    _yaml = None


def _mini_yaml(text: str) -> Dict[str, Any]:
    """极简 YAML 兜底解析器，仅支持本项目用到的 ``key: value`` / 列表 / 一层嵌套。

    安装了 PyYAML 时永远不会走到这里；它的存在只是为了让 ``make test`` 在
    最小依赖环境下也不至于直接崩溃。
    """
    root: Dict[str, Any] = {}
    stack = [(-1, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if line.startswith("- "):
            parent = stack[-1][1]
            if isinstance(parent, list):
                parent.append(_coerce(line[2:]))
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            child: Dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        elif value.startswith("[") and value.endswith("]"):
            parent[key] = [_coerce(v.strip()) for v in value[1:-1].split(",") if v.strip()]
        else:
            parent[key] = _coerce(value)
    return root


def _coerce(value: str) -> Any:
    value = value.strip()
    if value.startswith('"') and value.endswith('"') and len(value) > 1:
        return value[1:-1]
    if value.startswith("'") and value.endswith("'") and len(value) > 1:
        return value[1:-1]
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def load_yaml(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    if not path.is_absolute():
        path = CONFIG_DIR / path
    text = path.read_text(encoding="utf-8")
    if _yaml is not None:
        loaded = _yaml.safe_load(text)
        return loaded or {}
    return _mini_yaml(text)


@lru_cache(maxsize=None)
def city_config() -> Dict[str, Any]:
    return load_yaml("city.yaml")


@lru_cache(maxsize=None)
def model_config() -> Dict[str, Any]:
    return load_yaml("model.yaml")


@lru_cache(maxsize=None)
def rules_config() -> Dict[str, Any]:
    return load_yaml("rules.yaml")


def config_bundle() -> Dict[str, Any]:
    """一次性返回三份配置，供服务层与脚本共用。"""
    return {"city": city_config(), "model": model_config(), "rules": rules_config()}


def knowledge_base_path() -> Path:
    path = Path(rules_config()["knowledge_base"]["path"])
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_knowledge_base() -> Dict[str, Any]:
    path = knowledge_base_path()
    if not path.exists():  # 允许把知识库放在别处或被裁剪
        return {"version": "missing", "documents": []}
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 路径工具

def ensure_dirs() -> Dict[str, Path]:
    """创建工程运行所需的目录，返回 {名称: 路径}。"""
    paths = {
        "data_raw": DATA_DIR / "raw",
        "data_interim": DATA_DIR / "interim",
        "data_processed": DATA_DIR / "processed",
        "data_external": DATA_DIR / "external",
        "models": ARTIFACT_DIR / "models",
        "figures": ARTIFACT_DIR / "figures",
        "reports": ARTIFACT_DIR / "reports",
        "metrics": ARTIFACT_DIR / "metrics",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def artifact_path(*parts: str) -> Path:
    path = ARTIFACT_DIR.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def processed_path(name: str, suffix: str = "parquet") -> Path:
    directory = DATA_DIR / "processed"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{name}.{suffix}"


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def get_in(dct: Dict[str, Any], dotted: str, default: Optional[Any] = None) -> Any:
    """按 ``a.b.c`` 读取嵌套配置。"""
    node: Any = dct
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node
