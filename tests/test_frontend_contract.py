"""Small contract checks for the Streamlit presentation helpers."""

import importlib.util
from pathlib import Path


def _load_app_module():
    path = Path(__file__).parents[1] / "app.py"
    spec = importlib.util.spec_from_file_location("tianheng_app", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_quality_badges_keep_source_provenance_visible():
    app = _load_app_module()
    assert app._quality({"is_live": True, "source": "cma-authorised"}) == "LIVE"
    assert app._quality({"is_live": False, "source": "cma-cache", "provenance": {"label_quality": "cached"}}) == "CACHED"
    assert app._quality({"is_live": False, "source": "synthetic-radar", "provenance": {"label_quality": "synthetic"}}) == "SYNTHETIC"
    assert app._quality({"is_live": False, "source": "no-configured-feed", "provenance": {"label_quality": "unavailable"}}) == "UNAVAILABLE"
    assert app._quality({"is_live": False, "source": "no-configured-feed", "provenance": {"label_quality": "synthetic"}}) == "UNAVAILABLE"


def test_warning_meta_derives_countdown_and_release_state():
    app = _load_app_module()
    meta = app._warning_meta({"effective": "2000/01/01 00:00", "description": "未来1小时解除", "headline": "测试预警"})
    assert meta["state"] == "已解除"
    assert app._warning_remaining_text(meta) == "已过期"
