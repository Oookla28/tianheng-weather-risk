"""Tianheng internal weather-impact cockpit."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:  # pragma: no cover - optional until requirements are installed
    st_autorefresh = None

from src.agent.realtime import RealtimeWeatherAgent, WeatherSnapshot, deterministic_fallback
from src.radar.voxel import RadarVoxelCube
from src.service.risk_pipeline import RealtimeRiskService
from src.ui.public_data import fetch_public_bundle


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
    if "unavailable" in name or "no-configured" in name or label == "unavailable":
        return "UNAVAILABLE"
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
        html, body, [class*="css"], .stApp, .stApp * { font-family:"SimSun","宋体","Songti SC",serif !important; }
        .stApp { background:radial-gradient(circle at 15% 0%,#132747 0,#081221 43%,#060c16 100%); color:var(--ink); min-height:100vh; }
        [data-testid="stHeader"] { background:rgba(4,10,20,.7); }
        [data-testid="stSidebar"] { background:#081221; border-right:1px solid var(--line); }
        .block-container { max-width:1800px; padding-top:.75rem; padding-bottom:1.25rem; }
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
        .number-pulse { animation:numberPulse 2.2s ease-in-out infinite; }
        @keyframes numberPulse { 0%,100% { filter:brightness(1); transform:translateY(0); } 50% { filter:brightness(1.25); transform:translateY(-1px); } }
        .callout { border-left:3px solid #56b6ff; background:rgba(25,65,103,.28); padding:.65rem .8rem; border-radius:0 10px 10px 0; color:#c8dcf5; font-size:.82rem; }
        .warning-callout { border-left-color:#fb923c; background:rgba(131,64,21,.2); }
        .audit { color:#8298b7; font-size:.7rem; border-top:1px solid var(--line); padding-top:.7rem; margin-top:1rem; }
        .timeline { position:relative; display:flex; justify-content:space-between; gap:0; padding:1rem .4rem .35rem; margin:.2rem 0 .9rem; }
        .timeline:before { content:""; position:absolute; left:5%; right:5%; top:1.55rem; height:2px; background:linear-gradient(90deg,#4ade80 0 58%,#facc15 58% 78%,#334c6e 78%); }
        .timeline-item { position:relative; z-index:1; width:23%; text-align:center; color:#a6bbd8; font-size:.72rem; }
        .timeline-dot { width:.72rem; height:.72rem; border-radius:50%; margin:0 auto .42rem; background:#334c6e; border:2px solid #6f86a5; }
        .timeline-item.done .timeline-dot { background:#4ade80; border-color:#b9f6cd; box-shadow:0 0 12px #4ade80; }
        .timeline-item.active .timeline-dot { background:#facc15; border-color:#fff1a6; box-shadow:0 0 14px #facc15; animation:numberPulse 1.8s infinite; }
        .timeline-label { color:#dceaff; font-size:.8rem; font-weight:700; }
        .timeline-time { color:#8298b7; font-size:.66rem; margin-top:.16rem; }
        .map-shell { border:1px solid #29496d; border-radius:16px; overflow:hidden; background:#0a1527; }
        .layer-bar { display:flex; gap:.45rem; flex-wrap:wrap; padding:.55rem .7rem; border:1px solid var(--line); border-radius:12px; background:rgba(10,21,39,.85); margin-bottom:.65rem; }
        .flow-key { color:#7dd3fc; font-size:.72rem; letter-spacing:.02em; }
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


@st.cache_data(ttl=600, show_spinner=False)
def _public_bundle(latitude: float, longitude: float) -> dict[str, Any]:
    """Cache public weather/OSM calls for ten minutes to respect service limits."""
    return fetch_public_bundle(latitude, longitude)


def _source_frame(sources: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, source in sources.items():
        provenance = source.get("provenance") or {}
        rows.append({"来源": name, "状态": _quality(source), "原始 source": source.get("source", "unknown"), "实时": bool(source.get("is_live", False)), "标签质量": provenance.get("label_quality", "unknown"), "更新时间": source.get("retrieved_at") or source.get("observed_at") or "未提供", "缓存年龄(s)": provenance.get("cache_age_seconds", "—"), "说明": provenance.get("reason", "")})
    return pd.DataFrame(rows)


def _metric_card(label: str, value: str, detail: str = "", colour: str = "#e7eefb") -> None:
    st.markdown(f"<div class='panel' style='padding:.68rem .82rem'><div class='mini-label'>{label}</div><div class='mini-value number-pulse' style='color:{colour}'>{value}</div><div class='mini-label'>{detail}</div></div>", unsafe_allow_html=True)


def _radar_cube(payload: dict[str, Any], latitude: float, longitude: float) -> RadarVoxelCube | None:
    if str(payload.get("radar", {}).get("source", "")).startswith("synthetic"):
        return RadarVoxelCube.synthetic(origin_lat=latitude, origin_lon=longitude)
    return None


def _radar_figure(cube: RadarVoxelCube, frame_index: int) -> go.Figure:
    frame = cube.values[frame_index, 0]
    fig = go.Figure(go.Heatmap(z=frame, colorscale=[[0, "#091425"], [.18, "#155e75"], [.42, "#22c55e"], [.65, "#facc15"], [.82, "#fb923c"], [1, "#fb7185"]], zmin=0, zmax=70, colorbar={"title": "dBZ", "thickness": 12}, hovertemplate="网格 x=%{x}<br>网格 y=%{y}<br>反射率=%{z:.1f} dBZ<extra></extra>"))
    fig.update_layout(height=470, margin={"l":12, "r":12, "t":12, "b":12}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis={"title":"网格 x", "showgrid":False}, yaxis={"title":"网格 y", "autorange":"reversed", "showgrid":False})
    return fig


def _demo_layers(latitude: float, longitude: float) -> dict[str, Any]:
    """Create transparent demo GIS layers around the selected point.

    The basemap is real OpenStreetMap.  These overlays are deliberately marked
    as demo layers until authorised city GeoJSON feeds are connected.
    """
    boundary = [
        (latitude - .018, longitude - .025),
        (latitude + .014, longitude - .028),
        (latitude + .022, longitude + .018),
        (latitude - .010, longitude + .030),
        (latitude - .018, longitude - .025),
    ]
    roads = []
    for index, offset in enumerate((-.014, -.004, .008, .018)):
        roads.append({"name": f"主干道 {index + 1}", "lat": [latitude - .025, latitude + .025], "lon": [longitude + offset - .01, longitude + offset + .015]})
    roads.extend([
        {"name": "环城路", "lat": [latitude - .014, latitude + .016, latitude + .021], "lon": [longitude - .025, longitude + .002, longitude + .025]},
        {"name": "滨河路", "lat": [latitude - .020, latitude - .004, latitude + .020], "lon": [longitude - .028, longitude - .004, longitude + .023]},
    ])
    hospitals = [
        {"name": "市中心医院", "lat": latitude + .006, "lon": longitude - .008, "risk": "高"},
        {"name": "北城医院", "lat": latitude + .016, "lon": longitude + .016, "risk": "中"},
        {"name": "滨河急救中心", "lat": latitude - .013, "lon": longitude + .011, "risk": "中"},
    ]
    flows = [
        {"lat": [latitude - .012, latitude - .003, latitude + .008], "lon": [longitude - .020, longitude - .008, longitude + .004]},
        {"lat": [latitude + .022, latitude + .015, latitude + .008], "lon": [longitude - .020, longitude - .005, longitude + .013]},
    ]
    return {"boundary": boundary, "roads": roads, "hospitals": hospitals, "flows": flows}


def _map_figure(payload: dict[str, Any], latitude: float, longitude: float, *, show_radar: bool, show_admin: bool, show_roads: bool, show_hospitals: bool, show_flow: bool, public: dict[str, Any] | None = None) -> go.Figure:
    """Build a real basemap with switchable demo operational layers."""
    layers = _demo_layers(latitude, longitude)
    osm_result = (public or {}).get("osm", {})
    osm_data = osm_result.get("data") or {}
    if osm_result.get("status") == "LIVE":
        layers["hospitals"] = osm_data.get("hospitals", [])
        layers["roads"] = osm_data.get("roads", [])
        layers["boundaries"] = osm_data.get("boundaries", [])
    else:
        if osm_data.get("hospitals"):
            layers["hospitals"] = osm_data["hospitals"]
        if osm_data.get("roads"):
            layers["roads"] = osm_data["roads"]
        if osm_data.get("boundaries"):
            layers["boundaries"] = osm_data["boundaries"]
    fig = go.Figure()
    cube = _radar_cube(payload, latitude, longitude)
    if show_radar and cube is not None:
        frame = cube.values[-1, 0]
        rows, cols = frame.shape
        radar_lat, radar_lon, radar_value = [], [], []
        lat_scale = 1000 / 111_000
        lon_scale = lat_scale / max(0.25, np.cos(np.deg2rad(latitude)))
        for y in range(0, rows, 2):
            for x in range(0, cols, 2):
                radar_lat.append(latitude + (rows / 2 - y) * lat_scale)
                radar_lon.append(longitude + (x - cols / 2) * lon_scale)
                radar_value.append(float(frame[y, x]))
        fig.add_trace(go.Scattermap(lat=radar_lat, lon=radar_lon, mode="markers", name="雷达回波（演示）", marker={"size": 10, "color": radar_value, "colorscale": [[0, "#12304b"], [.35, "#22c55e"], [.62, "#facc15"], [.82, "#fb923c"], [1, "#fb7185"]], "cmin": 0, "cmax": 70, "opacity": .46, "colorbar": {"title": "dBZ"}}, hovertemplate="反射率 %{marker.color:.1f} dBZ<extra></extra>"))
    if show_admin:
        if layers.get("boundaries"):
            for index, boundary_item in enumerate(layers["boundaries"]):
                fig.add_trace(go.Scattermap(lat=boundary_item["lat"], lon=boundary_item["lon"], mode="lines", name="行政区边界（OSM）" if index == 0 else boundary_item.get("name", "行政区"), line={"width": 3, "color": "#60a5fa"}, hovertemplate=f"{boundary_item.get('name', '行政区')}<extra></extra>", showlegend=index == 0))
        else:
            boundary = layers["boundary"]
            fig.add_trace(go.Scattermap(lat=[item[0] for item in boundary], lon=[item[1] for item in boundary], mode="lines", name="行政区边界（演示）", line={"width": 3, "color": "#60a5fa"}, hoverinfo="skip"))
    if show_roads:
        for road in layers["roads"]:
            fig.add_trace(go.Scattermap(lat=road["lat"], lon=road["lon"], mode="lines", name=road["name"], line={"width": 2, "color": "#9fb7d5"}, hovertemplate=f"{road['name']}<extra></extra>", showlegend=False))
    if show_hospitals:
        if layers["hospitals"]:
            fig.add_trace(go.Scattermap(lat=[item["lat"] for item in layers["hospitals"]], lon=[item["lon"] for item in layers["hospitals"]], mode="markers+text", name="医院", text=[item["name"] for item in layers["hospitals"]], textposition="top center", marker={"size": 13, "color": [RISK_COLOURS[item["risk"]] for item in layers["hospitals"]]}, hovertemplate="%{text}<extra></extra>"))
    if show_flow:
        phase = int(pd.Timestamp.now().timestamp() * 2) % 2
        for index, flow in enumerate(layers["flows"]):
            lat_values = flow["lat"] if phase == 0 or index == 0 else list(reversed(flow["lat"]))
            lon_values = flow["lon"] if phase == 0 or index == 0 else list(reversed(flow["lon"]))
            fig.add_trace(go.Scattermap(lat=lat_values, lon=lon_values, mode="lines+markers", name="汇流方向", line={"width": 3, "color": "#22d3ee"}, marker={"size": 8, "color": "#67e8f9"}, hovertemplate="地表汇流方向（演示）<extra></extra>", showlegend=index == 0))
    fig.add_trace(go.Scattermap(lat=[latitude], lon=[longitude], mode="markers+text", name="当前研判点", text=["当前研判点"], textposition="bottom center", marker={"size": 16, "color": "#f8fafc", "allowoverlap": True}, hovertemplate="当前研判点<extra></extra>"))
    fig.update_layout(
        height=610,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        map={"style": "open-street-map", "center": {"lat": latitude, "lon": longitude}, "zoom": 11.2},
        legend={"orientation": "h", "y": .02, "x": .02, "bgcolor": "rgba(4,12,24,.76)", "font": {"color": "#dceaff", "size": 10}},
    )
    return fig


def _warning_timeline(warnings: list[dict[str, Any]] | None = None) -> None:
    final_label = f"已发布 · {len(warnings)} 条" if warnings else "未发布"
    final_time = "CMA公开预警" if warnings else "等待正式发布"
    st.markdown(
        f"""
        <div class='timeline'>
          <div class='timeline-item done'><div class='timeline-dot'></div><div class='timeline-label'>趋势提示</div><div class='timeline-time'>08:00 · 已完成</div></div>
          <div class='timeline-item done'><div class='timeline-dot'></div><div class='timeline-label'>灾害提醒</div><div class='timeline-time'>09:30 · 已完成</div></div>
          <div class='timeline-item active'><div class='timeline-dot'></div><div class='timeline-label'>预警研判</div><div class='timeline-time'>当前 · 待会商</div></div>
          <div class='timeline-item {'done' if warnings else ''}'><div class='timeline-dot'></div><div class='timeline-label'>正式发布</div><div class='timeline-time'>{final_label} · {final_time}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _three_d_figure(cube: RadarVoxelCube) -> go.Figure:
    values = cube.values[-1]
    z, y, x = np.indices(values.shape)
    fig = go.Figure(go.Isosurface(x=x.reshape(-1), y=y.reshape(-1), z=z.reshape(-1), value=values.reshape(-1), isomin=34, isomax=72, surface_count=3, colorscale=[[0, "#155e75"], [.45, "#22c55e"], [.72, "#facc15"], [1, "#fb7185"]], caps={"x": {"show": False}, "y": {"show": False}, "z": {"show": False}}, opacity=.72, hovertemplate="x=%{x}<br>y=%{y}<br>高度层=%{z}<br>反射率=%{value:.1f} dBZ<extra></extra>"))
    fig.update_layout(height=390, margin={"l": 0, "r": 0, "t": 10, "b": 0}, paper_bgcolor="rgba(0,0,0,0)", scene={"xaxis": {"title": "网格 x", "color": "#9fb7d5"}, "yaxis": {"title": "网格 y", "color": "#9fb7d5"}, "zaxis": {"title": "高度层", "color": "#9fb7d5"}, "bgcolor": "rgba(0,0,0,0)"}, showlegend=False)
    return fig


def _render_header(payload: dict[str, Any], offline: bool, public: dict[str, Any] | None = None) -> None:
    location = payload.get("location", {})
    badge_sources = list(payload.get("sources", {}).values())
    if public:
        badge_sources.extend(public.get(name, {}) for name in ("weather", "osm", "geocode", "warnings"))
    badge_html = "".join(_quality_badge(value) for value in badge_sources if value)
    mode = "离线演示" if offline else "授权源运行"
    place = ((public or {}).get("geocode", {}).get("data") or {}).get("display_name", "")
    place_text = f" · {place.split(',')[0]}" if place else ""
    st.markdown(f"<div class='topbar'><div><span class='topbar-title'>天衡 · 城市天气影响研判台</span><span class='topbar-sub'>内部决策支持 · {mode}{place_text} · {location.get('latitude', 0):.4f}, {location.get('longitude', 0):.4f}</span></div><div class='status-row'>{badge_html}</div></div>", unsafe_allow_html=True)
    if offline:
        st.info("离线演示模式：天气、雷达和排水结果会明确标记为 SYNTHETIC。")
    else:
        st.warning("授权数据源运行中：正式发布仍需要预报员审核、预警签发和审计留痕。")


def _render_cockpit(payload: dict[str, Any], latitude: float, longitude: float, public: dict[str, Any] | None = None) -> None:
    risk, snapshot, impact = payload["risk"], payload["risk"]["snapshot"], payload["impact"]
    level = risk.get("risk_level", "未知")
    cube = _radar_cube(payload, latitude, longitude)
    warnings = ((public or {}).get("warnings", {}).get("data") or {}).get("warnings", [])
    warning_rank = {"红色": 4, "橙色": 3, "黄色": 2, "蓝色": 1}
    highest_warning = max(warnings, key=lambda item: warning_rank.get(item.get("level", ""), 0), default=None)
    st.markdown("## 城市气象灾害值班总览")
    st.caption("实时监测 · 影响研判 · 预警流程 · 联动处置")

    metric_cols = st.columns(5)
    with metric_cols[0]:
        if highest_warning:
            warning_colour = {"红色": "#fb7185", "橙色": "#fb923c", "黄色": "#facc15", "蓝色": "#60a5fa"}.get(highest_warning.get("level"), "#e7eefb")
            _metric_card("官方预警", f"{highest_warning.get('level', '未知')} · {len(warnings)}条", "CMA公开接口", warning_colour)
        else:
            _metric_card("官方预警", "暂无", "CMA公开接口", "#4ade80")
    with metric_cols[1]:
        _metric_card("模型风险", level, f"概率 {risk.get('risk_probability', 0):.1%}", _risk_colour(level))
    with metric_cols[2]:
        _metric_card("雷达对流", f"{payload.get('radar', {}).get('convective_score', 0):.3f}", "当前体素评分", "#7dd3fc")
    with metric_cols[3]:
        _metric_card("峰值溢流", f"{impact.get('peak_overflow_mm', 0):.1f} mm", "基线排水情景", "#fb923c")
    with metric_cols[4]:
        _metric_card("置信度", f"{risk.get('confidence', 0):.1%}", "天气数据快照", "#c4b5fd")

    st.markdown("### 预警进程")
    _warning_timeline(warnings)

    layer_cols = st.columns(6)
    with layer_cols[0]:
        show_radar = st.toggle("雷达回波", value=True, key="home_radar")
    with layer_cols[1]:
        show_admin = st.toggle("行政区", value=True, key="home_admin")
    with layer_cols[2]:
        show_roads = st.toggle("道路", value=True, key="home_roads")
    with layer_cols[3]:
        show_hospitals = st.toggle("医院", value=True, key="home_hospitals")
    with layer_cols[4]:
        show_flow = st.toggle("汇流动画", value=True, key="home_flow")
    with layer_cols[5]:
        show_3d = st.toggle("三维对流体", value=False, key="home_3d")

    map_col, status_col = st.columns([2.35, .85])
    with map_col:
        st.markdown("<div class='map-shell'>", unsafe_allow_html=True)
        st.plotly_chart(_map_figure(payload, latitude, longitude, show_radar=show_radar, show_admin=show_admin, show_roads=show_roads, show_hospitals=show_hospitals, show_flow=show_flow, public=public), use_container_width=True, config={"displaylogo": False, "scrollZoom": True})
        st.markdown("</div>", unsafe_allow_html=True)
        osm_status = (public or {}).get("osm", {}).get("status", "UNAVAILABLE")
        osm_note = "已拉取 OSM 公开图层" if osm_status == "LIVE" else "未拉取到 OSM 图层，当前显示演示覆盖层"
        st.caption(f"真实 OpenStreetMap 底图 · {osm_note} · OSM 数据遵循 ODbL 1.0")
    with status_col:
        st.markdown("<div class='panel'><div class='panel-title'>值班状态</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='hero-label'>当前模型风险</div><div class='hero-level' style='font-size:2.2rem;--risk-colour:{_risk_colour(level)}'>{level}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='mini-label'>降水 / 风速</div><div class='mini-value'>{snapshot.get('precipitation_mm', 0):.1f} mm · {snapshot.get('wind_speed_kmh', 0):.1f} km/h</div>", unsafe_allow_html=True)
        st.markdown("<hr style='border-color:#203452'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-title'>重点对象</div>", unsafe_allow_html=True)
        osm_live = (public or {}).get("osm", {}).get("status") == "LIVE"
        osm_hospitals = ((public or {}).get("osm", {}).get("data") or {}).get("hospitals", [])
        hospital_value = "OSM 公开数据" if osm_live and osm_hospitals else ("OSM 当前范围未返回" if osm_live else "演示对象")
        for name, value in (("医院图层", hospital_value), ("道路图层", "OSM 公开数据" if osm_live else "演示道路"), ("排水泵站", "待接入")):
            st.markdown(f"<div style='display:flex;justify-content:space-between;border-bottom:1px solid #203452;padding:.48rem 0'><span class='mini-label'>{name}</span><span style='color:#facc15;font-size:.75rem'>{value}</span></div>", unsafe_allow_html=True)
        if warnings:
            for warning in warnings[:3]:
                st.markdown(f"<div class='callout warning-callout' style='margin-top:.55rem'><b>{warning.get('level', '未知')} · {warning.get('title', '公开预警')}</b><br>{warning.get('effective', '')}<br>{warning.get('description', '')[:100]}...</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='callout warning-callout' style='margin-top:.75rem'><b>官方预警：暂无</b><br>模型风险不等于红/橙/黄/蓝预警。</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if show_3d and cube is not None:
        st.markdown("### 三维对流体")
        st.plotly_chart(_three_d_figure(cube), use_container_width=True, config={"displaylogo": False})
        st.caption("三维视图展示当前演示雷达体素的对流结构，生产环境应使用授权三维雷达产品。")

    bottom_left, bottom_right = st.columns([1.15, 1])
    with bottom_left:
        st.markdown("### 研判依据")
        st.markdown(" · ".join(risk.get("main_reasons", [])))
        st.caption("模型方法：" + str(risk.get("evidence", {}).get("method", "unknown")))
    with bottom_right:
        st.markdown("### 数据健康")
        source_values = list(payload.get("sources", {}).values())
        if public:
            source_values.extend(public.get(name, {}) for name in ("weather", "osm", "geocode", "warnings"))
        st.markdown(" ".join(_quality_badge(value) for value in source_values if value), unsafe_allow_html=True)

    if public:
        with st.expander("公开小时预报（Open-Meteo）", expanded=False):
            weather_data = (public.get("weather", {}).get("data") or {})
            hourly = pd.DataFrame(weather_data.get("hourly", []))
            if not hourly.empty:
                hourly["time"] = pd.to_datetime(hourly["time"], errors="coerce")
                forecast_fig = px.line(hourly, x="time", y=["temperature_c", "precipitation_mm"], markers=True, labels={"value": "数值", "time": "本地时间", "variable": "指标"}, title="未来 24 小时公开预报")
                forecast_fig.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(forecast_fig, use_container_width=True, config={"displaylogo": False})
                st.caption("来源：Open-Meteo Forecast API；小时预报用于前端参考，不替代授权业务预报。")
            else:
                st.info("公开天气接口暂不可用，已保留模型/演示结果。")


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
    page = st.sidebar.radio("工作台", ["值班总览", "雷达与短临", "内涝排水情景", "影响与资产", "数据质量与证据"], label_visibility="collapsed")
    st.sidebar.divider()
    offline = st.sidebar.toggle("离线演示模式", value=False, key="offline_mode_v2", help="开启后不请求外部服务，并将结果明确标记为 SYNTHETIC。")
    public_enabled = st.sidebar.toggle("公开数据层", value=True, key="public_data_v1", help="从 Open-Meteo、OpenStreetMap Overpass 和 Nominatim 获取天气、医院、道路、行政区和位置名称。")
    auto_refresh = st.sidebar.toggle("自动刷新", value=False, key="auto_refresh_v1", help="按设定间隔刷新天气、公开预警和 OSM 数据。")
    refresh_seconds = st.sidebar.select_slider("刷新间隔", options=[60, 120, 300, 600], value=120, format_func=lambda value: f"{value // 60} 分钟")
    if auto_refresh and st_autorefresh is not None:
        st_autorefresh(interval=refresh_seconds * 1000, key="weather_refresh_timer")
    elif auto_refresh:
        st.sidebar.warning("自动刷新需要安装 streamlit-autorefresh；当前仍可使用手动刷新。")
    latitude = st.sidebar.number_input("纬度", value=43.88, min_value=-90.0, max_value=90.0, format="%.5f")
    longitude = st.sidebar.number_input("经度", value=125.32, min_value=-180.0, max_value=180.0, format="%.5f")
    if st.sidebar.button("刷新研判", type="primary", use_container_width=True):
        _run.clear(); _public_bundle.clear(); st.rerun()
    st.sidebar.markdown("<div class='audit'>模型风险 ≠ 官方预警<br>当前后端：单点服务</div>", unsafe_allow_html=True)
    with st.spinner("正在生成研判结果…"):
        payload = _run(float(latitude), float(longitude), offline)
    public = _public_bundle(float(latitude), float(longitude)) if public_enabled and not offline else None
    _render_header(payload, offline, public)
    if page == "值班总览": _render_cockpit(payload, float(latitude), float(longitude), public)
    elif page == "雷达与短临": _render_radar(payload, float(latitude), float(longitude))
    elif page == "内涝排水情景": _render_drainage(payload)
    elif page == "影响与资产": _render_assets(payload)
    else: _render_quality(payload)


if __name__ == "__main__":
    main()
