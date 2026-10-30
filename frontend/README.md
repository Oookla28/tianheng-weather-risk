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
