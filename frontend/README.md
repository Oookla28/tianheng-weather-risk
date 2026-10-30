# Tianheng Streamlit MVP

Run from the repository root:

```bash
python -m streamlit run app.py
```

The default **offline demo mode** uses deterministic synthetic weather and
radar data. Turn it off only when authorised live-source environment variables
are configured. Every source is labelled `LIVE`, `CACHED`, `SYNTHETIC`, or
`UNAVAILABLE` in the UI.

The current backend is a point-based research service. This MVP therefore does
not claim to be a city-wide risk grid, an official warning publisher, or a
production 30/60/120-minute forecast system. Official warnings must remain a
separate, human-reviewed workflow.

## 页面

- **值班驾驶舱**：风险主卡、来源健康、雷达网格示意、排水影响和官方预警状态
- **雷达与短临**：历史回波摘要、帧回放、对流核心和透明平流基线
- **内涝排水情景**：基线、提前抽排、进水口堵塞和降雨变化的过程曲线与差值
- **影响与资产**：明确显示当前单点 API 与资产 GeoJSON 尚未接入
- **数据质量与证据**：来源状态、缓存年龄、标签质量、模型证据和完整响应

The visual theme is a dark duty-room layout. The interface never presents a
synthetic or cached result as an official warning, and it does not claim a
city-wide risk grid until the backend exposes spatial risk and asset APIs.

## 首页值班大屏

首页采用宋体和深色全屏值班台布局，主视觉为 OpenStreetMap 底图，提供可开关的雷达回波、行政区边界、道路、医院和汇流演示图层。首页同时展示趋势提示—灾害提醒—预警研判—正式发布时间轴，并可展开三维对流体查看雷达体素结构。

OpenStreetMap 是真实底图；行政区、道路、医院和汇流覆盖层当前是演示数据，待授权 GIS/资产接口接入后替换。模型风险、缓存数据和合成数据仍不会被包装成正式气象预警。
