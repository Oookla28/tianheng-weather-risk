"""Tianheng internal weather-risk cockpit.

This is a small Streamlit presentation layer for the public backend.  It keeps
model risk, source quality, and official-warning status visibly separate.  The
repository currently exposes a point-based service, so the UI deliberately
labels the demo as a decision-support view rather than a city-wide warning
system.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from src.agent.realtime import RealtimeWeatherAgent, WeatherSnapshot, deterministic_fallback
from src.radar.voxel import RadarVoxelCube
from src.service.risk_pipeline import RealtimeRiskService


class _OfflineWeatherProvider:
    """Provider used by the explicit offline demo mode."""

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        return deterministic_fallback(latitude, longitude, reason="offline_demo_mode")


def _quality(source: dict[str, Any]) -> str:
    if source.get("is_live"):
        return "LIVE"
    name = str(source.get("source", "")).lower()
    label = str((source.get("provenance") or {}).get("label_quality", "")).lower()
    if "cache" in name or label == "cached":
        return "CACHED"
    if "synthetic" in name or label == "synthetic":
        return "SYNTHETIC"
    return "UNAVAILABLE"


def _quality_badge(source: dict[str, Any]) -> str:
    return f"{_quality(source)} · {source.get('source', 'unknown')}"


@st.cache_data(show_spinner=False)
def _run(latitude: float, longitude: float, offline: bool) -> dict[str, Any]:
    agent = RealtimeWeatherAgent(provider=_OfflineWeatherProvider()) if offline else None
    service = RealtimeRiskService(weather_agent=agent, use_environment_sources=not offline)
    return service.run(latitude, longitude, use_live_sources=not offline)


def _source_frame(sources: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, source in sources.items():
        provenance = source.get("provenance") or {}
        rows.append(
            {
                "来源": name,
                "状态": _quality(source),
                "source": source.get("source", "unknown"),
                "实时": bool(source.get("is_live", False)),
                "标签质量": provenance.get("label_quality", "unknown"),
                "更新时间": source.get("retrieved_at") or source.get("observed_at") or "未提供",
                "缓存年龄(s)": provenance.get("cache_age_seconds", "—"),
                "说明": provenance.get("reason", ""),
            }
        )
    return pd.DataFrame(rows)


def _risk_colour(level: str) -> str:
    return {"极高": "#b91c1c", "高": "#ea580c", "中": "#ca8a04", "低": "#15803d"}.get(level, "#475569")


def _render_header(payload: dict[str, Any], offline: bool) -> None:
    st.title("天衡 · 城市天气影响研判台")
    st.caption("内部决策支持 · 单点风险演示 · 模型风险不等于官方气象预警")
    if offline:
        st.info("当前为离线演示：天气、雷达和排水结果均会明确标记为 SYNTHETIC。")
    else:
        st.warning("正式业务使用前，请配置授权 CMA/市政数据源并完成值班员审核、校准和安全评估。")

    sources = payload.get("sources", {})
    st.write("数据源状态：", "　".join(_quality_badge(value) for value in sources.values()))


def _render_cockpit(payload: dict[str, Any]) -> None:
    risk = payload["risk"]
    snapshot = risk["snapshot"]
    impact = payload["impact"]
    level = risk.get("risk_level", "未知")
    st.subheader("值班驾驶舱")

    columns = st.columns(6)
    columns[0].metric("模型风险", level)
    columns[1].metric("风险概率", f"{risk.get('risk_probability', 0):.1%}")
    columns[2].metric("置信度", f"{risk.get('confidence', 0):.1%}")
    columns[3].metric("降水", f"{snapshot.get('precipitation_mm', 0):.1f} mm")
    columns[4].metric("峰值溢流", f"{impact.get('peak_overflow_mm', 0):.1f} mm")
    columns[5].metric("淹没面积", f"{impact.get('flooded_area_fraction', 0):.1%}")

    left, right = st.columns([1.4, 1])
    with left:
        st.markdown("#### 当前天气与研判依据")
        weather = pd.DataFrame(
            {
                "指标": ["温度", "降水概率", "风速", "湿度", "数据来源"],
                "值": [
                    f"{snapshot.get('temperature_c', 0):.1f} °C",
                    f"{snapshot.get('precipitation_probability', 0):.1%}",
                    f"{snapshot.get('wind_speed_kmh', 0):.1f} km/h",
                    f"{snapshot.get('humidity_percent', 0):.1f}%",
                    str(snapshot.get("source", "unknown")),
                ],
            }
        )
        st.dataframe(weather, hide_index=True, use_container_width=True)
        st.write("主要原因：", "、".join(risk.get("main_reasons", [])))
        st.caption("当前服务将 official_warning 固定标记为 False；正式预警必须经过业务审核和发布流程。")

    with right:
        st.markdown("#### 影响指标")
        st.metric("影响等级", impact.get("risk_level", "未知"))
        st.metric("模型排水等级", impact.get("model_risk_level", "未知"))
        observed = payload.get("sources", {}).get("drainage", {})
        if observed.get("source") == "no-configured-feed":
            st.warning("暂无授权市政排水观测，观测积水不能解释为 0。")
        else:
            st.metric("观测最大水深", f"{impact.get('observed_water_depth_mm', 0):.1f} mm")

    st.markdown("#### 当前点位")
    st.json(payload.get("location", {}), expanded=False)


def _render_radar(payload: dict[str, Any], latitude: float, longitude: float) -> None:
    st.subheader("雷达与短临")
    radar = payload["radar"]
    summary = pd.DataFrame(radar.get("summary", []))
    if summary.empty:
        st.info("当前数据源没有返回雷达摘要。")
        return
    summary["timestamp"] = pd.to_datetime(summary["timestamp"], errors="coerce")
    st.caption(f"雷达来源：{radar.get('source', 'unknown')} · 对流分数：{radar.get('convective_score', 0):.3f}")
    chart = px.line(
        summary,
        x="timestamp",
        y=["max_reflectivity", "mean_reflectivity"],
        markers=True,
        labels={"value": "反射率（dBZ）", "timestamp": "时间", "variable": "指标"},
        title="雷达反射率时间序列",
    )
    st.plotly_chart(chart, use_container_width=True)

    metric = st.selectbox("查看指标", ["convective_fraction", "core_count"], format_func=lambda x: {"convective_fraction": "对流像元比例", "core_count": "对流核心数"}[x])
    metric_chart = px.bar(summary, x="timestamp", y=metric, labels={metric: "值", "timestamp": "时间"})
    st.plotly_chart(metric_chart, use_container_width=True)

    st.markdown("#### 当前帧示意图")
    if str(radar.get("source", "")).startswith("synthetic"):
        cube = RadarVoxelCube.synthetic(origin_lat=latitude, origin_lon=longitude)
        frame = cube.values[-1, 0]
        heatmap = px.imshow(frame, color_continuous_scale="Turbo", labels={"x": "网格 x", "y": "网格 y", "color": "dBZ"})
        heatmap.update_layout(title="合成雷达当前帧（仅用于演示）")
        st.plotly_chart(heatmap, use_container_width=True)
    else:
        st.info("当前服务返回雷达摘要和元数据，未返回原始体素值；生产前端应通过独立雷达帧接口绘制原始回波。")
    st.caption("当前 nowcast 是透明平流基线，不能直接视为正式 30/60/120 分钟预报。")


def _render_drainage(payload: dict[str, Any]) -> None:
    st.subheader("内涝排水情景")
    counterfactuals = payload.get("counterfactuals", {})
    if not counterfactuals:
        st.info("暂无排水情景结果。")
        return
    labels = {
        "baseline": "基线",
        "early_pumping": "提前抽排",
        "blocked_inlets": "进水口堵塞",
        "rainfall_minus_20pct": "降雨减少 20%",
    }
    selected = st.multiselect("选择情景", list(counterfactuals), default=list(counterfactuals))
    metric = st.selectbox(
        "过程指标",
        ["rainfall_mm", "runoff_mm", "capacity_mm", "storage_mm", "overflow_mm", "flooded_area_fraction"],
        format_func=lambda x: {
            "rainfall_mm": "降雨量（mm）",
            "runoff_mm": "产流量（mm）",
            "capacity_mm": "排水能力（mm）",
            "storage_mm": "蓄水量（mm）",
            "overflow_mm": "溢流量（mm）",
            "flooded_area_fraction": "淹没面积比例",
        }[x],
    )
    rows: list[dict[str, Any]] = []
    for scenario in selected:
        for step in counterfactuals[scenario].get("steps", []):
            rows.append({"情景": labels.get(scenario, scenario), **step})
    if rows:
        frame = pd.DataFrame(rows)
        chart = px.line(frame, x="minute", y=metric, color="情景", markers=True, labels={"minute": "分钟", metric: metric})
        st.plotly_chart(chart, use_container_width=True)

    summary_rows = []
    for scenario, result in counterfactuals.items():
        summary_rows.append(
            {
                "情景": labels.get(scenario, scenario),
                "峰值溢流(mm)": result.get("peak_overflow_mm", 0),
                "峰值蓄水(mm)": result.get("peak_storage_mm", 0),
                "累计淹没面积比例": result.get("total_flooded_area_fraction", 0),
            }
        )
    st.dataframe(pd.DataFrame(summary_rows), hide_index=True, use_container_width=True)
    st.caption("情景结果是模型筛查输出；实测积水仍需来自授权市政排水观测。")


def _render_quality(payload: dict[str, Any]) -> None:
    st.subheader("数据质量与证据链")
    st.dataframe(_source_frame(payload.get("sources", {})), hide_index=True, use_container_width=True)
    st.markdown("#### 风险证据")
    st.json(payload.get("risk", {}).get("evidence", {}), expanded=True)
    st.markdown("#### 免责声明")
    st.warning(payload.get("disclaimer", "研究与决策支持结果，不构成官方预警。"))
    st.info("生产部署前还需要授权数据、事件级校准、正式水动力验证、值班员审核、权限控制和审计留痕。")


def main() -> None:
    st.set_page_config(page_title="天衡天气影响研判台", page_icon="🌧️", layout="wide")
    st.sidebar.title("研判台")
    page = st.sidebar.radio("页面", ["值班驾驶舱", "雷达与短临", "内涝排水情景", "数据质量与证据"])
    offline = st.sidebar.toggle("离线演示模式", value=True)
    latitude = st.sidebar.number_input("纬度", value=43.88, min_value=-90.0, max_value=90.0, format="%.5f")
    longitude = st.sidebar.number_input("经度", value=125.32, min_value=-180.0, max_value=180.0, format="%.5f")
    if st.sidebar.button("刷新研判"):
        _run.clear()

    with st.spinner("正在生成研判结果…"):
        payload = _run(float(latitude), float(longitude), offline)
    _render_header(payload, offline)
    if page == "值班驾驶舱":
        _render_cockpit(payload)
    elif page == "雷达与短临":
        _render_radar(payload, float(latitude), float(longitude))
    elif page == "内涝排水情景":
        _render_drainage(payload)
    else:
        _render_quality(payload)


if __name__ == "__main__":
    main()
