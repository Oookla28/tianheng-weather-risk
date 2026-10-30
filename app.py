"""Tianheng internal weather-impact cockpit."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.agent.realtime import RealtimeWeatherAgent, WeatherSnapshot, deterministic_fallback
from src.radar.voxel import RadarVoxelCube
from src.service.risk_pipeline import RealtimeRiskService


RISK_COLOURS = {"极高": "#fb7185", "高": "#fb923c", "中": "#facc15", "低": "#4ade80"}
QUALITY_COLOURS = {"LIVE": "#4ade80", "CACHED": "#facc15", "SYNTHETIC": "#a78bfa", "UNAVAILABLE": "#94a3b8"}
SCENARIO_LABELS = {"baseline": "基线", "early_pumping": "提前抽排", "blocked_inlets": "进水口堵塞", "rainfall_minus_20pct": "降雨减少 20%"}


class _OfflineWeatherProvider:
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


def _risk_colour(level: str) -> str:
    return RISK_COLOURS.get(level, "#94a3b8")


def _quality_badge(source: dict[str, Any]) -> str:
    quality = _quality(source)
    return (
        f"<span class='status-pill' style='--pill-colour:{QUALITY_COLOURS[quality]}'><span class='status-dot'></span>"
        f"{quality}<small>{source.get('source', 'unknown')}</small></span>"
    )


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root { --ink:#e7eefb; --muted:#8fa4c4; --line:#203452; }
        .stApp { background:radial-gradient(circle at 15% 0%,#132747 0,#081221 43%,#060c16 100%); color:var(--ink); }
        [data-testid="stHeader"] { background:rgba(4,10,20,.7); }
        [data-testid="stSidebar"] { background:#081221; border-right:1px solid var(--line); }
        .block-container { max-width:1500px; padding-top:1.5rem; padding-bottom:2rem; }
        h1 { font-size:2.2rem !important; }
        h2 { font-size:1.45rem !important; }
        h3 { font-size:1.05rem !important; color:#cfe0f8; }
        [data-testid="stMetric"] { background:rgba(16,27,46,.86); border:1px solid var(--line); border-radius:14px; padding:12px 14px; }
        [data-testid="stMetricLabel"] { color:var(--muted); }
        [data-testid="stMetricValue"] { color:var(--ink); }
        .topbar { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.65rem .9rem; border:1px solid var(--line); background:rgba(16,27,46,.72); border-radius:14px; margin-bottom:1rem; }
        .topbar-title { font-size:.88rem; color:#cfe0f8; font-weight:650; }
        .topbar-sub { display:block; font-size:.72rem; color:var(--muted); margin-top:.2rem; }
        .status-row { display:flex; flex-wrap:wrap; gap:.45rem; justify-content:flex-end; }
        .status-pill { display:inline-flex; align-items:center; gap:.38rem; border:1px solid color-mix(in srgb,var(--pill-colour) 42%,#203452); border-radius:999px; padding:.28rem .55rem; font-size:.68rem; color:var(--pill-colour); background:rgba(8,18,34,.86); white-space:nowrap; }
        .status-pill small { color:#9bb0cc; font-size:.63rem; margin-left:.1rem; }
        .status-dot { width:.42rem; height:.42rem; border-radius:50%; background:var(--pill-colour); box-shadow:0 0 9px var(--pill-colour); }
        .hero { border:1px solid #29496d; background:linear-gradient(135deg,rgba(19,54,88,.9),rgba(16,27,46,.92)); border-radius:18px; padding:1.2rem 1.35rem; min-height:178px; }
        .hero-label { color:#9db7d8; font-size:.76rem; text-transform:uppercase; letter-spacing:.08em; }
        .hero-level { font-size:2.6rem; line-height:1.05; font-weight:800; color:var(--risk-colour); margin:.35rem 0; }
        .hero-number { color:#f6fbff; font-size:1.25rem; font-weight:700; }
        .hero-note { color:#abc0db; font-size:.78rem; line-height:1.55; margin-top:.55rem; }
        .panel { border:1px solid var(--line); background:rgba(16,27,46,.84); border-radius:16px; padding:1rem 1.05rem; }
        .panel-title { color:#d9e8fb; font-size:.9rem; font-weight:700; margin-bottom:.65rem; }
        .mini-label { color:var(--muted); font-size:.72rem; }
        .mini-value { color:#e9f3ff; font-weight:700; font-size:1.05rem; }
        .callout { border-left:3px solid #56b6ff; background:rgba(25,65,103,.28); padding:.65rem .8rem; border-radius:0 10px 10px 0; color:#c8dcf5; font-size:.82rem; }
        .warning-callout { border-left-color:#fb923c; background:rgba(131,64,21,.2); }
        .audit { color:#8298b7; font-size:.7rem; border-top:1px solid var(--line); padding-top:.7rem; margin-top:1rem; }
        div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:12px; overflow:hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def _run(latitude: float, longitude: float, offline: bool) -> dict[str, Any]:
    agent = RealtimeWeatherAgent(provider=_OfflineWeatherProvider()) if offline else None
    service = RealtimeRiskService(weather_agent=agent, use_environment_sources=not offline)
    return service.run(latitude, longitude, use_live_sources=not offline)


def _source_frame(sources: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, source in sources.items():
        provenance = source.get("provenance") or {}
        rows.append({"来源": name, "状态": _quality(source), "原始 source": source.get("source", "unknown"), "实时": bool(source.get("is_live", False)), "标签质量": provenance.get("label_quality", "unknown"), "更新时间": source.get("retrieved_at") or source.get("observed_at") or "未提供", "缓存年龄(s)": provenance.get("cache_age_seconds", "—"), "说明": provenance.get("reason", "")})
    return pd.DataFrame(rows)


def _metric_card(label: str, value: str, detail: str = "", colour: str = "#e7eefb") -> None:
    st.markdown(f"<div class='panel' style='padding:.78rem .9rem'><div class='mini-label'>{label}</div><div class='mini-value' style='color:{colour}'>{value}</div><div class='mini-label'>{detail}</div></div>", unsafe_allow_html=True)


def _radar_cube(payload: dict[str, Any], latitude: float, longitude: float) -> RadarVoxelCube | None:
    if str(payload.get("radar", {}).get("source", "")).startswith("synthetic"):
        return RadarVoxelCube.synthetic(origin_lat=latitude, origin_lon=longitude)
    return None


def _radar_figure(cube: RadarVoxelCube, frame_index: int) -> go.Figure:
    frame = cube.values[frame_index, 0]
    fig = go.Figure(go.Heatmap(z=frame, colorscale=[[0, "#091425"], [.18, "#155e75"], [.42, "#22c55e"], [.65, "#facc15"], [.82, "#fb923c"], [1, "#fb7185"]], zmin=0, zmax=70, colorbar={"title": "dBZ", "thickness": 12}, hovertemplate="网格 x=%{x}<br>网格 y=%{y}<br>反射率=%{z:.1f} dBZ<extra></extra>"))
    fig.update_layout(height=470, margin={"l":12, "r":12, "t":12, "b":12}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis={"title":"网格 x", "showgrid":False}, yaxis={"title":"网格 y", "autorange":"reversed", "showgrid":False})
    return fig


def _render_header(payload: dict[str, Any], offline: bool) -> None:
    location = payload.get("location", {})
    badge_html = "".join(_quality_badge(value) for value in payload.get("sources", {}).values())
    mode = "离线演示" if offline else "授权源运行"
    st.markdown(f"<div class='topbar'><div><span class='topbar-title'>天衡 · 城市天气影响研判台</span><span class='topbar-sub'>内部决策支持 · {mode} · {location.get('latitude', 0):.4f}, {location.get('longitude', 0):.4f}</span></div><div class='status-row'>{badge_html}</div></div>", unsafe_allow_html=True)
    if offline:
        st.info("离线演示模式：天气、雷达和排水结果会明确标记为 SYNTHETIC。")
    else:
        st.warning("授权数据源运行中：正式发布仍需要预报员审核、预警签发和审计留痕。")


def _render_cockpit(payload: dict[str, Any], latitude: float, longitude: float) -> None:
    risk, snapshot, impact = payload["risk"], payload["risk"]["snapshot"], payload["impact"]
    level, colour = risk.get("risk_level", "未知"), _risk_colour(risk.get("risk_level", "未知"))
    st.markdown("## 值班驾驶舱")
    st.caption("现在发生什么 → 未来如何变化 → 会影响什么 → 数据是否可信 → 下一步动作")
    hero, metrics = st.columns([1.05, 1.95])
    with hero:
        st.markdown(f"<div class='hero' style='--risk-colour:{colour}'><div class='hero-label'>模型风险 · 当前点位</div><div class='hero-level'>{level}</div><div class='hero-number'>{risk.get('risk_probability', 0):.1%} <span style='font-size:.78rem;color:#abc0db'>概率 · 置信度 {risk.get('confidence', 0):.1%}</span></div><div class='hero-note'>{'、'.join(risk.get('main_reasons', []))}</div></div>", unsafe_allow_html=True)
    with metrics:
        m1, m2, m3 = st.columns(3)
        with m1:
            _metric_card("当前降水", f"{snapshot.get('precipitation_mm', 0):.1f} mm", "天气快照")
            _metric_card("降水概率", f"{snapshot.get('precipitation_probability', 0):.1%}", "当前小时")
        with m2:
            _metric_card("峰值溢流", f"{impact.get('peak_overflow_mm', 0):.1f} mm", "基线情景")
            _metric_card("模型淹没面积", f"{impact.get('flooded_area_fraction', 0):.1%}", "筛查结果")
        with m3:
            _metric_card("风速", f"{snapshot.get('wind_speed_kmh', 0):.1f} km/h", "10m 风")
            _metric_card("湿度", f"{snapshot.get('humidity_percent', 0):.1f}%", "相对湿度")
    st.markdown("### 监测地图与影响判断")
    map_col, side_col = st.columns([1.6, 1])
    with map_col:
        cube = _radar_cube(payload, latitude, longitude)
        if cube is not None:
            st.plotly_chart(_radar_figure(cube, len(cube.timestamps) - 1), use_container_width=True, config={"displaylogo": False})
            st.caption("合成雷达网格示意 · 不是城市级实况风险场 · 选择雷达与短临页查看时间轴")
        else:
            st.info("当前雷达源未返回原始体素值。生产前端应接入独立雷达栅格接口后显示地图。")
        st.markdown("<div class='callout warning-callout'><b>官方预警：暂无接入</b><br>模型风险仅用于内部研判，不等同于红/橙/黄/蓝气象预警。</div>", unsafe_allow_html=True)
    with side_col:
        st.markdown("<div class='panel'><div class='panel-title'>影响与处置状态</div>", unsafe_allow_html=True)
        st.metric("综合影响等级", impact.get("risk_level", "未知"))
        st.metric("模型排水等级", impact.get("model_risk_level", "未知"))
        drainage_source = payload.get("sources", {}).get("drainage", {})
        if drainage_source.get("source") == "no-configured-feed":
            st.warning("暂无授权市政排水观测；观测水深不可解释为 0。")
        else:
            st.metric("观测最大水深", f"{impact.get('observed_water_depth_mm', 0):.1f} mm")
        st.markdown("<div class='mini-label'>当前服务范围</div><div class='mini-value'>单点研判</div><br><div class='mini-label'>资产接口</div><div class='mini-value'>未接入</div></div>", unsafe_allow_html=True)
    reasons_col, audit_col = st.columns([1.1, 1])
    with reasons_col:
        st.markdown("### 研判依据")
        for reason in risk.get("main_reasons", []):
            st.markdown(f"- {reason}")
        st.caption("模型方法：" + str(risk.get("evidence", {}).get("method", "unknown")))
    with audit_col:
        st.markdown("### 运行审计")
        st.json({"location": payload.get("location"), "official_warning": risk.get("evidence", {}).get("official_warning", False), "radar_source": payload.get("radar", {}).get("source")}, expanded=False)


def _render_radar(payload: dict[str, Any], latitude: float, longitude: float) -> None:
    st.markdown("## 雷达与短临")
    radar = payload["radar"]
    summary = pd.DataFrame(radar.get("summary", []))
    if summary.empty:
        st.info("当前数据源没有返回雷达摘要。"); return
    summary["timestamp"] = pd.to_datetime(summary["timestamp"], errors="coerce")
    st.caption(f"来源：{radar.get('source', 'unknown')} · 维度：{radar.get('shape', 'unknown')} · 对流分数：{radar.get('convective_score', 0):.3f}")
    left, right = st.columns([1.35, 1])
    with left:
        chart = px.line(summary, x="timestamp", y=["max_reflectivity", "mean_reflectivity"], markers=True, labels={"value":"反射率（dBZ）", "timestamp":"时间", "variable":"指标"}, title="历史回波摘要")
        chart.update_layout(height=340, margin={"l":10, "r":10, "t":50, "b":10}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(chart, use_container_width=True, config={"displaylogo": False})
    with right:
        trend = px.area(summary, x="timestamp", y="convective_fraction", markers=True, labels={"convective_fraction":"比例", "timestamp":"时间"}, title="对流像元比例")
        trend.update_layout(height=340, margin={"l":10, "r":10, "t":50, "b":10}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(trend, use_container_width=True, config={"displaylogo": False})
    cube = _radar_cube(payload, latitude, longitude)
    if cube is not None:
        st.markdown("### 回波帧回放")
        frame_index = st.slider("选择历史帧", 0, len(cube.timestamps) - 1, len(cube.timestamps) - 1)
        frame_col, info_col = st.columns([1.45, 1])
        with frame_col:
            st.plotly_chart(_radar_figure(cube, frame_index), use_container_width=True, config={"displaylogo": False})
        with info_col:
            selected = summary.iloc[frame_index]
            _metric_card("帧时间", str(selected.get("timestamp", "—")), "UTC")
            _metric_card("最大反射率", f"{float(selected.get('max_reflectivity', 0)):.1f} dBZ", "当前层")
            _metric_card("对流核心", f"{int(selected.get('core_count', 0))}", "连通区域")
            st.markdown("<div class='callout'>当前演示数据为合成雷达体素。授权实时源下，服务仅返回摘要和元数据，生产环境需提供原始雷达帧接口。</div>", unsafe_allow_html=True)
        nowcast_rows = [{"分钟": index * 5, "最大反射率": item.max_reflectivity, "对流比例": item.convective_fraction} for index, item in enumerate(cube.nowcast(horizons=3).summary(), start=1)]
        st.markdown("### 短临外推基线")
        st.plotly_chart(px.line(pd.DataFrame(nowcast_rows), x="分钟", y=["最大反射率", "对流比例"], markers=True, labels={"value":"值", "分钟":"未来分钟"}), use_container_width=True)
        st.caption("当前实现是透明平流基线，仅展示未来 15 分钟演示结果，不能包装成正式 30/60/120 分钟预报。")


def _render_drainage(payload: dict[str, Any]) -> None:
    st.markdown("## 内涝排水情景")
    counterfactuals = payload.get("counterfactuals", {})
    if not counterfactuals:
        st.info("暂无排水情景结果"); return
    baseline_peak = float(counterfactuals.get("baseline", {}).get("peak_overflow_mm", 0))
    comparison = st.columns(len(counterfactuals))
    for column, (name, result) in zip(comparison, counterfactuals.items()):
        peak = float(result.get("peak_overflow_mm", 0)); delta = 0 if name == "baseline" else baseline_peak - peak
        with column: _metric_card(SCENARIO_LABELS.get(name, name), f"{peak:.1f} mm", f"峰值溢流 · Δ {delta:+.1f} mm", "#fb923c" if peak > baseline_peak else "#4ade80")
    tab_trend, tab_compare = st.tabs(["过程曲线", "情景比较"])
    with tab_trend:
        selected = st.multiselect("选择情景", list(counterfactuals), default=list(counterfactuals), format_func=lambda x: SCENARIO_LABELS.get(x, x))
        metric = st.selectbox("过程指标", ["rainfall_mm", "runoff_mm", "capacity_mm", "storage_mm", "overflow_mm", "flooded_area_fraction"], format_func=lambda x: {"rainfall_mm":"降雨量（mm）", "runoff_mm":"产流量（mm）", "capacity_mm":"排水能力（mm）", "storage_mm":"蓄水量（mm）", "overflow_mm":"溢流量（mm）", "flooded_area_fraction":"淹没面积比例"}[x])
        rows = [{"情景": SCENARIO_LABELS.get(scenario, scenario), **step} for scenario in selected for step in counterfactuals[scenario].get("steps", [])]
        if rows:
            fig = px.line(pd.DataFrame(rows), x="minute", y=metric, color="情景", markers=True, labels={"minute":"分钟", metric:metric})
            fig.update_layout(height=430, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
    with tab_compare:
        summary_rows = []
        for scenario, result in counterfactuals.items():
            peak = float(result.get("peak_overflow_mm", 0))
            summary_rows.append({"情景":SCENARIO_LABELS.get(scenario, scenario), "峰值溢流(mm)":peak, "峰值蓄水(mm)":result.get("peak_storage_mm", 0), "累计淹没面积比例":result.get("total_flooded_area_fraction", 0), "相对基线改善(mm)":baseline_peak - peak})
        st.dataframe(pd.DataFrame(summary_rows), hide_index=True, use_container_width=True)
        st.caption("情景结果是模型筛查输出；实测积水仍需来自授权市政排水观测。")


def _render_assets(payload: dict[str, Any]) -> None:
    st.markdown("## 影响对象与资产")
    st.warning("当前公开后端还是单点风险服务，尚未提供医院、学校、道路、泵站等资产 GeoJSON 和逐网格 RiskAssessment。")
    left, right = st.columns(2)
    with left:
        st.markdown(f"<div class='panel'><div class='panel-title'>当前可用对象</div><div class='mini-label'>位置</div><div class='mini-value'>当前查询点</div><br><div class='mini-label'>风险等级</div><div class='mini-value'>{payload.get('risk', {}).get('risk_level', '未知')}</div><br><div class='mini-label'>影响等级</div><div class='mini-value'>{payload.get('impact', {}).get('risk_level', '未知')}</div></div>", unsafe_allow_html=True)
    with right:
        st.markdown("<div class='panel'><div class='panel-title'>下一步资产接口</div><div class='callout'>建议接入 /assets、/risk/grid 和 /action-plans，前端再按设施重要性、P50 风险、P10–P90 区间和预计影响时间生成检查队列。</div></div>", unsafe_allow_html=True)


def _render_quality(payload: dict[str, Any]) -> None:
    st.markdown("## 数据质量与证据链")
    sources = payload.get("sources", {})
    cards = st.columns(max(1, len(sources)))
    for column, (name, source) in zip(cards, sources.items()):
        quality = _quality(source)
        with column:
            st.markdown(f"<div class='panel'><div class='panel-title'>{name}</div><div class='hero-level' style='font-size:1.6rem;--risk-colour:{QUALITY_COLOURS[quality]}'>{quality}</div><div class='mini-label'>{source.get('source', 'unknown')}</div><div class='mini-label'>实时：{source.get('is_live', False)}</div></div>", unsafe_allow_html=True)
    st.markdown("### 来源明细")
    st.dataframe(_source_frame(sources), hide_index=True, use_container_width=True)
    with st.expander("展开风险证据", expanded=True): st.json(payload.get("risk", {}).get("evidence", {}), expanded=True)
    with st.expander("展开完整服务响应"): st.json(payload, expanded=False)
    st.markdown("<div class='audit'>研究与决策支持结果，不构成官方预警。生产部署需要授权数据、事件级校准、正式水动力验证、值班员审核、权限控制和审计留痕。</div>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="天衡天气影响研判台", page_icon="🌧️", layout="wide", initial_sidebar_state="expanded")
    _inject_styles()
    st.sidebar.markdown("## 天衡研判台")
    st.sidebar.caption("城市暴雨与内涝 · 内部决策支持")
    page = st.sidebar.radio("工作台", ["值班驾驶舱", "雷达与短临", "内涝排水情景", "影响与资产", "数据质量与证据"], label_visibility="collapsed")
    st.sidebar.divider()
    offline = st.sidebar.toggle("离线演示模式", value=True, help="开启后不请求外部服务，并将结果明确标记为 SYNTHETIC。")
    latitude = st.sidebar.number_input("纬度", value=43.88, min_value=-90.0, max_value=90.0, format="%.5f")
    longitude = st.sidebar.number_input("经度", value=125.32, min_value=-180.0, max_value=180.0, format="%.5f")
    if st.sidebar.button("刷新研判", type="primary", use_container_width=True):
        _run.clear(); st.rerun()
    st.sidebar.markdown("<div class='audit'>模型风险 ≠ 官方预警<br>当前后端：单点服务</div>", unsafe_allow_html=True)
    with st.spinner("正在生成研判结果…"):
        payload = _run(float(latitude), float(longitude), offline)
    _render_header(payload, offline)
    if page == "值班驾驶舱": _render_cockpit(payload, float(latitude), float(longitude))
    elif page == "雷达与短临": _render_radar(payload, float(latitude), float(longitude))
    elif page == "内涝排水情景": _render_drainage(payload)
    elif page == "影响与资产": _render_assets(payload)
    else: _render_quality(payload)


if __name__ == "__main__":
    main()
