# 天衡 Tianheng：可复现科研陈述与完整实验复现说明

> **作品题目**：基于多源气象—地形—排水数据融合的城市暴雨风险智能决策系统
>
> **英文题目**：Tianheng: Multi-source Weather, Terrain and Drainage Fusion for Urban Storm-impact Risk and Action Planning
>
> **项目简称**：天衡 Tianheng
>
> **本地研究包版本**：`866e5976682bab727d0b23144bbce0d4479b33e8`，提交信息为 `Prepare Tianheng research package for GitHub release`
>
> **公开仓库**：[Oookla28/tianheng-weather-risk](https://github.com/Oookla28/tianheng-weather-risk)
>
> **文档用途**：竞赛技术报告、论文方法部分、答辩复现说明和实验审计记录。
>
> **重要边界**：本文件描述本地完整研究包和公开后端包的共同方法基础。任何结果都必须同时标明数据性质：真实观测、公开模拟数据、合成演示、缓存数据或规则基线。模拟数据结果不能表述为官方预警准确率，合成雷达不能表述为真实 CMA 雷达观测，排水筛查模型不能表述为经过水力认证的 1D/2D 水动力模型。

---

## 1. 摘要

城市暴雨影响预报的难点不是缺少天气变量，而是天气变量与城市对象之间存在尺度、语义和决策鸿沟：气象产品通常是模型网格或区域观测，城市管理者关心的是哪一条道路、哪一家医院、哪一所学校可能先受到影响，以及应急资源怎样提前配置。积水水深和排水管网状态又通常具有较少、较碎片化或受权限限制的标签，直接把粗网格降水解释为街道级积水会产生过度精确的结论。

天衡把任务定义为一个从气象信号到行动的可审计闭环。给定天气实况 (W)、雷达或回波结构 (R)、地形与下垫面 (T)、城市设施图 (G) 和积水观测 (O)，系统对位置 (x) 在未来时间窗 (Delta) 内的城市影响事件进行概率或风险排序：

\[
Y_{t+\Delta}(x)=\mathbb{1}\{h_{t+\Delta}(x)\ge h_0\}
\]

\[
P_{t+\Delta}(x)=P(Y_{t+\Delta}(x)=1\mid W,R,T,G,O)
\]

系统最终输出四类结果：

1. **空间风险场**：网格级或对象级风险概率、风险等级和影响类型；
2. **关键设施优先级**：道路、医院、学校、泵站和排水节点的风险与关键性排序；
3. **排水与反事实结果**：正常排水、提前抽排、堵塞进水口、减雨或资源受限情景的差异；
4. **证据链**：数据来源、时间、版本、标签质量、缓存状态、模型状态和人工确认要求。

科研主线不是单纯追求一个指标，而是验证三个问题：

- 在暴雨事件标签稀缺、气象分辨率不一致的情况下，地形、下垫面和历史状态能否提升一步影响预测；
- 预测区间或风险置信度能否在未见事件上保持可解释的覆盖水平；
- 将预测结果传递给排水和资源约束行动规划后，能否降低关键设施暴露与响应成本。

---

## 2. 复现对象与事实边界

当前项目存在两个需要明确区分的代码层级。

### 2.1 本地完整研究包

本地完整研究包的当前提交为：

```text
866e5976682bab727d0b23144bbce0d4479b33e8
```

该版本共有 72 个 Git 跟踪文件，包含：

- Streamlit 本地演示入口；
- 实时天气 Agent；
- 风险模型、风险排序、证据链；
- 3D 雷达体素和 30/60/120 分钟短临基线；
- 城市排水数字孪生；
- 反事实行动模拟；
- UrbanFlood24 Lite HGB 实验脚本；
- GPU ConvGRU 训练脚本；
- 训练、评测、图表和报告产物；
- 10 个本地测试。

### 2.2 公开 GitHub 快照与本次提交边界

公开仓库当前 main 的实际文件应以远端树和逐文件审计为准。当前远端已经存在 `app.py` 和 `src/ui/public_data.py` 等既有界面文件，README 中关于“前端排除”的说明与实际树存在版本不一致。本次用户授权的动作只上传本科研陈述，不新增、修改或重新打包任何前端文件；本报告的技术主线仍然是后端算法、研究实验和复现证据。

公开仓库中的原始 UrbanFlood24 Lite 文件被 `.gitignore` 排除，原因是文件体积、数据许可和避免把外部原始数据重复分发；复现者必须根据 manifest 下载并校验原始数据。

公开仓库、当前本地完整研究包和本次新增文档不能简单视为同一份工作树。复现报告必须写明：

```text
代码版本：明确 Git commit SHA
原始数据：独立下载，记录 URL、下载时间和 SHA-256
实验产物：记录 checkpoint/report 的 SHA-256
前端：不属于本次新增内容；既有远端入口是否保留，以仓库维护者另行清理为准
```

本次陈述编写时，已通过 GitHub 文件接口逐文件读取并核对公开后端快照。关键 blob SHA 如下，复现者可以用 GitHub 页面或 API 再次核对：

| 公开文件 | blob SHA |
|---|---|
| `src/ingest/cma_radar.py` | `94d44659b4ce7bf2325fe656d554fa88b918a01a` |
| `src/ingest/changchun_drainage.py` | `073873f1a76740b438c0bdea360a6674f7ca641a` |
| `src/service/risk_pipeline.py` | `dcdb2c3efa150aef7bbfe3dd86fc7c7dc52abff9` |
| `src/radar/voxel.py` | `7738fae26c994e8bf7192e809a8e3ac9ed58240a` |
| `src/drainage/simulator.py` | `1e62a4acabd7ebca62d5400bf2adab1f1ef7b534` |
| `tests/test_live_adapters.py` | `80d12738fb7df614d4952c80e5d552e87ea15ddd` |
| `docs/DATA_ACCESS.md` | `cbc80102ebfdd0ded21abdf896f1dd3f8934633c` |
| `configs/live_sources.example.env` | `2fe3eda24241258bdc6e47d5b13cfaddd6ebe798` |

这张表只核对公开后端文件，不代表公开仓库包含本地 72 文件研究工作树，也不代表原始 UrbanFlood24 文件已上传。

### 2.3 状态标签

本文后续使用以下状态：

| 状态 | 含义 |
|---|---|
| `implemented` | 当前本地代码已经实现并有测试或报告证据 |
| `research-validated` | 已在公开模拟数据或演示事件上完成可复现实验 |
| `adapter-ready` | 数据契约、解析和缓存接口已经实现，但需要真实授权数据 |
| `requires-authorisation` | 数据源存在，但接口/token/导出权限尚未放入运行环境 |
| `planned` | README、论文或方案提出，但当前代码尚未完成 |

---

## 3. 研究假设、贡献和非目标

### 3.1 研究假设

**H1：** 在降雨输入不变时，当前水深、地形、下垫面和排水状态等环境状态特征，能比单纯持续性基线更好地预测下一步水深变化。

**H2：** 按完整暴雨事件划分训练、校准和测试，可以降低相邻时间片泄漏导致的虚高指标。

**H3：** 分裂校准区间可以把预测残差转换成可审计的不确定性范围；覆盖率和区间宽度需要同时报告。

**H4：** 将预测风险与设施关键性、资源数量、响应时间和道路可达性结合，能比单纯按概率阈值排序得到更可解释的行动方案。

**H5：** 数据来源状态和标签质量显式参与输出后，系统更容易区分实时决策、缓存回放、合成演示和科研弱标签。

### 3.2 主要研究贡献

1. **跨分辨率融合**：将天气和雷达时空结构、地形汇流、下垫面和城市对象统一到网格/设施风险表达中。
2. **双轨模型架构**：GPU ConvGRU 用于保持空间结构和时间演化，CPU HistGradientBoosting 残差模型用于快速复现和现场降级。
3. **不确定性进入服务契约**：将 P10/P50/P90、区间覆盖率、区间宽度和来源质量写入结果，而不是只输出一个分数。
4. **排水物理筛查与反事实**：用蓄水—排水—溢流关系约束风险解释，并比较提前抽排、堵塞进水口和资源限制场景。
5. **来源感知 Agent**：对天气、雷达、排水输入记录 live/cache/synthetic/unavailable 状态，网络失败时不伪造实时观测。
6. **事件级科研协议**：固定事件级划分、校准事件、测试事件、随机种子和指标口径，避免随机时间片泄漏。

### 3.3 非目标

当前版本不宣称：

- 发布中国气象局官方预警；
- 对真实长春城区给出已认证的街道级积水预报；
- 替代城市水务部门的 1D/2D 水动力模型；
- 用网页雷达图代替授权 CMA 体扫或网格产品；
- 将合成城市网络、合成雷达或模拟洪涝标签当作真实业务标签；
- 用一次单种子 GPU 运行结果证明跨城市泛化。

---

## 4. 环境与依赖

### 4.1 严格环境

`pyproject.toml` 指定：

```toml
requires-python = ">=3.11"
```

Dockerfile 采用 Python 3.11 slim。严格复现应使用 Python 3.11 或更高版本。此前本机有一次使用系统 Python 3.9.6 完成兼容性验证，但这不是项目声明的严格运行环境，论文和竞赛复现应使用 3.11。

### 4.2 CPU 环境

```bash
cd /path/to/AIC-2
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

核心依赖范围：

```text
numpy>=1.26,<3
pandas>=2.1,<3
scikit-learn>=1.4,<2
streamlit>=1.37,<2
plotly>=5.20,<7
pydantic>=2.5,<3
pyarrow>=14,<20
joblib>=1.3,<2
ortools>=9.8,<10
pytest>=8,<9
```

### 4.3 GPU 环境

GPU 训练在 CPU 依赖之外安装：

```bash
python -m pip install -r requirements-gpu.txt
```

其中：

```text
torch>=2.2
```

检查 CUDA：

```bash
python - <<'PY'
import torch
print(torch.__version__)
print("cuda_available=", torch.cuda.is_available())
print("device=", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")
PY
```

如果 CUDA 不可用，GPU 脚本会使用 CPU，但速度和显存路径不能与 RTX 4090 D 结果等同。

### 4.4 基础验证

```bash
python -m pytest -q
python -m compileall -q app.py
python -c "import app; print('app import ok')"
```

当前本地验收记录：

```text
10 passed
app.py compile: PASS
```

### 4.5 时区和随机数

- 事件演示时间使用 `datetime` 和 pandas 时间戳；
- 外部实时 Agent 的时间统一记录为 UTC ISO-8601；
- UrbanFlood24 事件时间按数据文件本身读取，不强行转换为本地时区；
- 演示数据随机种子为 `7`；
- 雷达合成体素默认种子为 `20261030`；
- GPU ConvGRU 默认种子为 `7`；
- HGB 随机状态为 `7`；
- 如果修改任何 seed，必须在报告和 artifact manifest 中记录。

---

## 5. 完整目录与文件责任

```text
app.py
README.md
pyproject.toml
requirements.txt
requirements-gpu.txt
Dockerfile
docker-compose.yml
Makefile

src/
  schemas.py              Event、Snapshot 等基础契约
  demo_data.py            固定种子合成事件、网格、设施和标签
  features.py             时间特征、网格特征和设施特征拼接
  models.py               RandomForest 风险模型与分裂校准区间
  risk.py                 网格/设施风险评分和文本原因
  optimize.py             资源约束贪心行动方案与校验
  service.py              演示服务编排
  live_agent.py           Open-Meteo 地理编码、实况、缓存和风险筛查
  radar_nowcast.py        多仰角雷达体积、短临集合和 Plotly 体素图
  drainage_twin.py        合成排水网络、径流压力、深度和 GeoJSON 层
  counterfactual.py       降雨、响应提前量、资源和道路封控反事实
  evaluation.py           AUC、F1、Brier、MAE、RMSE 和 Top-K
  evidence.py             评测、区间和数据溯源证据表
  visuals_3d.py           3D 场、剖面和时间线绘图

scripts/
  prepare_demo.py
  train_demo.py
  evaluate_demo.py
  replay_demo.py
  train_research.py
  evaluate_research.py
  train_urbanflood_lite.py
  train_convgru_urbanflood.py
  make_research_figures.py
  run_pipeline.py
  prepare_external_data.py
  fetch_weather.py

configs/
  live_sources.example.env

data/
  processed/              已生成的紧凑演示表
  external/               外部数据目录，原始 UrbanFlood24 被忽略
  cache/                  实时缓存，不应提交

artifacts/
  models/                 joblib、模型清单
  reports/                JSON、CSV 指标
  figures/                研究图表
  convgru_urbanflood.pt   GPU checkpoint
  convgru_urbanflood.json GPU 训练报告

docs/
  experiment-reproduction.md
  competition-proposal.md
  paper-draft.md
  defense-outline.md
  DEPLOYMENT.md

tests/
  test_smoke.py
  test_weather.py
  test_live_agent.py
  test_radar_nowcast.py
  test_drainage_twin.py
```

公开后端仓库还包含授权 CMA 雷达和长春排水适配器、后端服务契约和适配器测试。它们与本地完整研究包的概念边界一致，但文件集合和 commit 必须分别核对。

---

## 6. 数据准备

### 6.1 合成演示数据

`src/demo_data.py::generate_demo_bundle(seed=7)` 生成三个完整事件：

```text
demo-2024-0712  2024-07-12 暴雨过程
demo-2024-0819  2024-08-19 强对流过程
demo-2024-0905  2024-09-05 台风外围降雨
```

每个事件：

- 9 个时间片；
- 每 30 分钟一个时间片；
- 80 个网格单元，坐标为 `x=0..9, y=0..7`；
- 8 个设施对象；
- 3 个事件共 2160 条 rainfall 行；
- 216 条 asset label 行；
- 网格静态表 80 行；
- 设施表 8 行。

生成命令：

```bash
python scripts/prepare_demo.py
```

合成数据组成：

```python
rng = np.random.default_rng(7)
phase = max(0.0, np.sin((t + 1) / 9.0 * np.pi))
spatial_peak = np.exp(-((x - 4.3) ** 2 + (y - 3.2) ** 2) / 18.0)
rainfall = max(0.0, 5.0 + 43.0 * phase * spatial_peak * event_scale + noise)
```

设施标签由局地降雨、汇流和关键性共同生成：

```python
local_rain = 5.0 + 43.0 * phase * spatial_peak * event_scale
target_risk = clip(
    (local_rain / 60.0)
    * (1.0 + flow_accumulation * 0.35)
    * (0.8 + criticality * 0.3),
    0,
    1,
)
```

这些标签是 `label_quality=synthetic`，只能用来验证服务链、排序和测试，不能用于声称真实城市准确率。

### 6.2 UrbanFlood24 Lite

当前公开数据实验使用 UrbanFlood24 Lite：

```text
24 个训练事件 + 12 个测试事件
3 个 location/catchment
128 × 128 空间网格
10 分钟数据步长
flood.npy：水深时序
rainfall.npy：降雨时序
absolute_DEM.npy：高程
impervious.npy：不透水面
manhole.npy：检查井/排水相关静态特征
```

来源和文件哈希保存在：

```text
data/external/urbanflood24_lite_manifest.json
```

当前 manifest 记录：

```text
source_url: https://drive.google.com/file/d/1_P4tNlYCneCmKr2X9r-TAoiCKk1-AauI/view
archive: data/external/urbanflood24_lite_release.zip
bytes: 30986785
sha256: 760b8c583496461704cf8de36c6dbc272960495dae609da47525b48ead63e0a0
```

原始数据不在 Git 跟踪树中。复现者必须：

1. 从 manifest 记录的来源获取数据；
2. 将 release archive 放入指定路径；
3. 计算 SHA-256 并与 manifest 比较；
4. 解压到 `data/external/urbanflood24_lite/`；
5. 检查 `train/flood`、`train/geodata` 和 `test/flood` 目录结构；
6. 再运行训练脚本。

校验命令：

```bash
shasum -a 256 data/external/urbanflood24_lite_release.zip
```

注意：`scripts/prepare_external_data.py` 的完整 UrbanFlood24 下载路径是 `data/external/urbanflood24`，而 HGB/ConvGRU Lite 脚本读取 `data/external/urbanflood24_lite`。复现实验应以 `train_urbanflood_lite.py` 和 `train_convgru_urbanflood.py` 的 `--data-root` 为准，不能只运行 `prepare_external_data.py` 就假定目录已满足 Lite 脚本。

### 6.3 实时天气

`src/live_agent.py` 使用两个固定 HTTPS 接口：

```text
https://geocoding-api.open-meteo.com/v1/search
https://api.open-meteo.com/v1/forecast
```

地理编码参数：

```python
{
    "name": search_name,
    "count": 10,
    "language": "zh",
    "format": "json",
}
```

当输入“长春”或“长春市”时，代码将搜索名改为 `Changchun`，然后优先选择 `admin1` 包含“吉林”的结果，避免同名地点排序错误。

天气请求参数：

```python
{
    "latitude": round(latitude, 5),
    "longitude": round(longitude, 5),
    "current": "temperature_2m,precipitation,rain,wind_speed_10m,weather_code",
    "hourly": "precipitation,rain,temperature_2m,wind_speed_10m,weather_code",
    "forecast_days": 3,
    "timezone": "UTC",
}
```

缓存规则：

- 地理编码缓存有效期：24 小时；
- 预报缓存有效期：30 分钟；
- 网络失败时先尝试 stale cache；
- 没有缓存时返回 `cache_status=unavailable` 和错误步骤；
- Open-Meteo 结果记录 CC BY 4.0 许可提示、请求哈希、时间和坐标。

### 6.4 CMA 雷达与长春排水授权适配

公开后端包中的 `src/ingest/cma_radar.py` 支持：

- `CMA_RADAR_ENDPOINT`；
- `CMA_RADAR_TOKEN`；
- `CMA_RADAR_DATA_CODE`；
- `CMA_RADAR_TIME_RANGE`；
- `CMA_RADAR_STATION_IDS`；
- JSON 体素；
- `DS`/`fileInfos` 中的 `FILE_URL`；
- NPY/NPZ；
- 结果缓存和年龄限制。

长春排水适配器支持：

- CSV、JSON、GeoJSON；
- `latitude/lat/纬度`；
- `longitude/lon/lng/经度`；
- `water_depth_mm/积水深度毫米`；
- `depth_cm/积水深度/水深`；
- `CHANGCHUN_DRAINAGE_DEPTH_UNIT=cm/mm/m`；
- 实时、缓存、不可用状态；
- 观测深度、受淹点比例和原始行保留。

运行模板位于：

```text
configs/live_sources.example.env
```

这些适配器已经完成接口和 fixture 验收，但真正的 CMA 定量产品和长春市政管网/积水观测必须通过授权接口或批准的数据导出接入，不能用网页抓取替代。

---

## 7. 数据契约

### 7.1 Event

```python
@dataclass(frozen=True)
class Event:
    event_id: str
    label: str
    start: datetime
    end: datetime
    area: str
    data_version: str = "demo-v1"
    model_version: str = "rule-risk-v1"
    label_quality: str = "synthetic"
```

### 7.2 RadarVolume

```text
volume: float32[elevation, y, x]
x: 空间横坐标或经度
 y: 空间纵坐标或纬度
elevation: 仰角/高度层
timestamp: UTC datetime
source: radar_npz 或 synthetic
quality_flags: file_loaded / normalised_0_1 / synthetic_demo 等
metadata: 原数组键、原始最小值、原始最大值、文件路径
```

输入为四维 `(time,elevation,y,x)` 时，加载器默认取第一个时间帧作为当前体积；生产系统应把时间维度拆分为连续 `RadarVolume`，再交给集合短临模块。

### 7.3 NowcastResult

```text
horizon_minutes
valid_time
ensemble: [member,elevation,y,x]
mean
p10
p90
source
quality_flags
motion_vector
```

### 7.4 RiskModel 和风险表

网格风险表至少需要：

```text
rainfall_mm
rainfall_1h
rainfall_peak
elevation
slope
flow_accumulation
imperviousness
```

评分后增加：

```text
p10
risk_probability  # p50
p90
confidence
risk_level
main_reason
```

风险等级阈值：

```text
risk_probability >= 0.70  高
0.45 <= p < 0.70           中
p < 0.45                   低
```

设施风险在网格风险上增加关键性优先调整：

```python
p50_adjusted = clip(p50 * (0.88 + 0.12 * criticality), 0, 1)
```

### 7.5 DrainageTwin 图层

合成网络包含：

```text
manholes: manhole_id, x, y, invert_m, catchment_ha, storage_m3, capacity_m3s, geometry
pipes: pipe_id, from_manhole, to_manhole, diameter_m, capacity_m3s, length_m, slope, geometry
roads: road_id, name, road_class, criticality, geometry
outlets: outlet_id, capacity_m3s, tidal_backwater, geometry
pumps: pump_id, rated_m3s, efficiency, status, geometry
```

所有合成图层添加：

```text
data_origin = synthetic-demo
label_quality = synthetic
```

---

## 8. 算法实现细节

### 8.1 演示网格与空间特征

演示网格坐标为 `x=0..9`、`y=0..7`。静态特征由以下公式生成：

```python
elevation = 42.0 + 1.8 * y + 0.7 * x + 2.0 * sin(x / 2.5)
slope = 0.04 + abs(cos((x + y) / 3.0)) * 0.16
flow = 0.2 + (1.0 - y / 9.0) * 0.8 + 0.35 * I[x in {3,4,5}]
impervious = clip(0.35 + 0.05*x + 0.03*(7-y), 0.2, 0.95)
```

真实网格适配时，应把这些字段替换为 DEM、土地覆盖和水系计算结果，并保留相同列名或建立明确的字段映射。

### 8.2 时间特征

`src/features.py::snapshot_features`：

1. 选取指定 `time_index` 的 rainfall 当前切片；
2. 对 `time_index <= t` 的降雨按 `event_id,x,y` 聚合；
3. 计算 `rainfall_1h` 为当前事件窗口的累计值；
4. 计算 `rainfall_peak` 为当前窗口最大值；
5. 与 grid 静态特征按 `x,y` 合并。

`feature_matrix` 使用列：

```text
rainfall_mm
rainfall_1h
rainfall_peak
elevation
slope
flow_accumulation
imperviousness
```

归一化：

```python
rainfall_mm, rainfall_1h, rainfall_peak = clip(value / 60.0, 0, 2)
elevation = (elevation - 40.0) / 20.0
```

### 8.3 RiskModel 随机森林路径

训练：

```python
RandomForestRegressor(
    n_estimators=80,
    max_depth=8,
    random_state=7,
    n_jobs=1,
)
```

拟合后计算训练残差标准差：

```python
residual_scale = max(std(y - pred), 0.04)
```

校准：

1. 只在独立 calibration event 上预测；
2. 计算 `abs(y - pred)`；
3. 给定 `coverage=0.90`；
4. 使用有限样本校正分位数：

```python
level = min(1.0, coverage * (1.0 + 1.0 / n_calibration))
radius = max(quantile(abs_residual, level), 0.04)
```

区间：

```python
p10 = clip(p50 - radius, 0, 1)
p90 = clip(p50 + radius, 0, 1)
confidence = clip(1 - (p90 - p10), 0.35, 0.98)
```

没有 calibration radius 时，使用基于残差尺度和当前降雨的 fallback spread：

```python
spread = residual_scale + 0.05 * clip(rainfall_mm / 60.0, 0, 1)
radius = 1.28 * spread
```

该 fallback 是工程降级规则，不是正式校准结论。

### 8.4 实时 Agent 风险筛查

实时 Agent 先汇总：

```text
未来 6 小时累计降雨
未来 24 小时累计降雨
当前风速
WMO weather_code
```

规则筛查分数：

```python
rain_score = min(1, rain_6h / 35) * 0.58 \\
           + min(1, rain_24h / 100) * 0.27
wind_score = min(1, wind_ms / 20) * 0.10
weather_score = 0.05 if code >= 95 else 0.03 if code >= 80 else 0
score = clip(rain_score + wind_score + weather_score, 0, 1)
```

等级：

```text
score >= 0.78  极高
0.52–0.78      高
0.25–0.52      中
< 0.25         低
```

它的输出字段叫 `severe_weather_probability`，同时有：

```text
probability_label = 恶劣天气概率（筛查）
probability_status = 规则筛查，非官方预警概率
```

这两个字段必须在产品和报告中保留，不能把它写成校准后的官方概率。

### 8.5 雷达体素加载与短临

`src/radar_nowcast.py` 支持：

```text
data/radar/volume*.npz
```

加载逻辑：

1. 按文件修改时间取最新文件；
2. 优先查找 `volume/reflectivity/dbz/radar/data/values` 数组键；
3. 接受三维 `(elevation,y,x)`；
4. 接受四维 `(time,elevation,y,x)` 并取第一个帧；
5. NaN 和无穷值转为 0；
6. 如果原值不在 `[0,1]`，按 1%–99% 分位缩放到 `[0,1]`；
7. 找不到文件时生成 deterministic Gaussian storm cells，并设置 `quality_flags=(synthetic_demo,no_volume_npz,deterministic_seed)`。

默认形状：

```text
(elevation, y, x) = (8, 32, 32)
horizons = (30, 60, 120)
members = 5
motion_vector = (2.0, -0.8)
seed = 20261030
```

每个成员：

```python
steps = horizon / 30
Dx = motion_x * steps + Normal(0, 0.25*max(1,steps))
Dy = motion_y * steps + Normal(0, 0.20*max(1,steps))
translated = integer_zero_padded_translation(base, Dx, Dy)
decay = exp(-0.018*horizon) * (1 - 0.018*member)
noise = Normal(0, 0.008 + 0.002*steps)
ensemble_member = clip(translated*decay + noise, 0, 1)
```

输出均值、P10、P90和运动向量。该方法是可解释的 translation-decay baseline，不是 ConvGRU 的替代品，也不代表真实雷达校准结果。

### 8.6 UrbanFlood24 Lite HGB 残差模型

目标：

```text
target = flood[t+1] - flood[t]
```

每个样本特征顺序固定为：

```text
rainfall
rainfall_cumulative
rainfall_1h
current_depth
dem
impervious
manhole
x_norm
y_norm
```

`build_rows` 对每个事件的每个 `t` 生成空间网格行：

```python
rain_1h = rainfall[max(0,t-5):t+1].sum()
current = flood[t].reshape(-1)
x = [rainfall[t], cumulative, rain_1h, current, dem, impervious, manhole, x_norm, y_norm]
y = flood[t+1].reshape(-1)
```

训练模型：

```python
HistGradientBoostingRegressor(
    max_iter=160,
    learning_rate=0.08,
    max_leaf_nodes=63,
    l2_regularization=1e-3,
    random_state=7,
)
```

模型学习的是残差：

```python
model.fit(x_fit, y_fit - current_depth)
pred = clip(current_depth + model.predict(x), 0, None)
```

划分实际代码：

```text
train_events[:-2]  fit
train_events[-2:]  calibration
all test events     test
```

因此 HGB Lite 的实际事件划分是 **22 fit / 2 calibration / 12 test**，不能和 ConvGRU 的 21/3/12 混写。

校准半径：

```python
level = min(1, 0.90 * (1 + 1/n_residuals))
radius = max(quantile(abs_residual, level), 1e-4)
```

预测区间：

```python
lo = clip(pred - radius, 0, None)
hi = pred + radius
```

### 8.7 GPU ConvGRU

训练脚本：

```text
scripts/train_convgru_urbanflood.py
```

事件划分：

```text
fit_events = train_events[:-3]  # 21
val_events = train_events[-3:]   # 3
test_events = test_events        # 12
```

窗口：

```text
seq_len = 6
每个窗口输入过去 6 个 10 分钟时间步，即约 60 分钟历史
```

每个时间步输入 7 个通道：

```text
1. flood depth
2. rainfall
3. DEM
4. impervious
5. manhole
6. x_norm
7. y_norm
```

尺度：

```text
depth_scale = 2.0
rain_scale = 40.0
```

模型结构：

```text
ConvGRUCell(in_channels=7, hidden_channels=hidden)
ConvGRUCell(in_channels=hidden, hidden_channels=hidden)
Conv2d(hidden, hidden, kernel=3, padding=1)
GroupNorm(8, hidden)
ReLU
Conv2d(hidden, 1, kernel=1)
```

每个时间步更新两个隐藏状态，最后用残差预测：

```python
prediction = x[:, -1, :1] + head(hidden_state)
```

训练参数：

```text
epochs=12
batch_size=2
hidden=32
lr=2e-3
AdamW(weight_decay=1e-4)
Huber/Smooth-L1 loss
max gradient norm=1.0
CUDA AMP when available
seed=7
```

选择最佳模型的标准是 validation MAE。测试只在最佳验证状态恢复后执行一次。

### 8.8 排水数字孪生

合成排水网络用 `DrainageTwin.synthetic(seed=42,n=6)` 创建 (6\times6) 个检查井，生成相邻水平/垂直管线、道路、两个排水口和两个泵站。

默认降雨：

```text
28 mm/h 设计降雨 × rainfall_multiplier
```

流量：

```python
rain_mps = 0.028 * rainfall_multiplier / 3600
runoff_m3s = rain_mps * catchment_ha * 10000 * 0.78 * temporal
```

其中：

```python
temporal = 0.78 + 0.22 * min(nowcast_horizon,180) / 180
```

排水压力：

```python
drain_stress = clip(runoff_m3s / capacity_m3s, 0, 3)
```

节点积水深度：

```python
water_depth_m = clip(
    max(runoff_m3s - capacity_m3s, 0)
    * horizon * 60 / storage_m3
    * 0.018,
    0,
    1.2,
)
```

压力等级：

```text
<0.45  蓝色
0.45–0.80 黄色
0.80–1.20 橙色
>=1.20 红色
```

管线流量来自起点检查井径流：

```python
pipe.flow_m3s = source_runoff * (1.10 + 0.025 * pipe_index)
```

该模块输出表格和 GeoJSON，适合风险可视化、筛查和反事实；不是水力认证模型。

### 8.9 反事实和行动规划

`simulate_counterfactual` 的参数：

```text
rainfall_multiplier: 0.5–2.0
response_lead_minutes: >=0
resource_budget: >=0
road_closure: bool
```

动作对风险的影响：

```python
risk_grid *= rainfall_multiplier
risk_asset *= rainfall_multiplier
if response_lead_minutes > 0:
    risk_grid *= 0.95
if resource_budget > 0:
    top_budget_assets *= (1 - min(0.45, 0.08 + lead/240))
if road_closure:
    road_risk *= 0.72
```

`generate_plan` 资源上限：

```python
RESOURCE_LIMITS = {
    "排水车": 2,
    "巡检组": 3,
    "交通管控组": 2,
}
```

风险优先策略：

```python
plan_score = 0.80 * risk_probability + 0.20 * criticality
```

资源均衡策略：

```python
plan_score = 0.65 * risk_probability + 0.35 * criticality
```

每个动作记录：

```text
sequence
action
resource
target_id
target
asset_type
priority
start_after_min
duration_min
reason
status=待人工确认
generation_seconds
```

---

## 9. 完整运行流程

### 9.1 最小离线演示

```bash
python3 scripts/prepare_demo.py
python3 scripts/train_demo.py
python3 scripts/evaluate_demo.py
python3 scripts/replay_demo.py
```

### 9.2 研究风险模型

```bash
python3 scripts/train_research.py
python3 scripts/evaluate_research.py
```

`train_research.py` 使用三场完整演示事件：

```text
train: demo-2024-0712
calibration: demo-2024-0819
test: demo-2024-0905
```

每个事件 72 行设施时刻样本，模型产物：

```text
artifacts/models/risk_model_research.joblib
artifacts/reports/research_split.json
artifacts/reports/research_predictions.csv
artifacts/reports/research_metrics.json
```

### 9.3 UrbanFlood24 HGB

确认数据目录存在后：

```bash
python3 scripts/train_urbanflood_lite.py \\
  --data-root data/external/urbanflood24_lite \\
  --max-train-rows 250000 \\
  --max-iter 160
```

输出：

```text
artifacts/models/urbanflood_lite_depth.joblib
artifacts/reports/urbanflood_lite_metrics.json
artifacts/reports/urbanflood_lite_event_metrics.csv
```

### 9.4 GPU ConvGRU

完整训练：

```bash
python3 scripts/train_convgru_urbanflood.py \\
  --data-root data/external/urbanflood24_lite \\
  --seq-len 6 \\
  --epochs 12 \\
  --batch-size 2 \\
  --hidden 32 \\
  --lr 2e-3 \\
  --seed 7 \\
  --output-prefix artifacts/convgru_urbanflood
```

快速 smoke：

```bash
python3 scripts/train_convgru_urbanflood.py \\
  --data-root data/external/urbanflood24_lite \\
  --epochs 4 \\
  --batch-size 4 \\
  --hidden 16 \\
  --seed 7 \\
  --output-prefix artifacts/convgru_urbanflood_smoke
```

输出：

```text
artifacts/convgru_urbanflood.pt
artifacts/convgru_urbanflood.json
```

### 9.5 研究流水线

```bash
python3 scripts/run_pipeline.py --skip-urbanflood
```

它依次执行：

```text
prepare_demo.py
train_demo.py
evaluate_demo.py
train_research.py
evaluate_research.py
```

如果不加 `--skip-urbanflood`，只有在 `data/external/urbanflood24_lite` 存在时才运行 HGB Lite，否则打印跳过信息。GPU ConvGRU 不由 `run_pipeline.py` 自动运行，必须单独执行训练命令。

### 9.6 本地驾驶舱

```bash
streamlit run app.py --server.port 8501
```

当前入口主要展示位置输入、实时天气风险、影响区域和 Agent 步骤日志；其他历史/雷达/排水工作区函数存在于代码中，但以当前 `main()` 路由为准，不应在答辩中声称所有隐藏工作区都已作为产品入口开放。

---

## 10. 现有实验结果

### 10.1 本地测试

```text
python3 -m pytest -q
.......... [100%]
10 passed
```

测试覆盖：

- 排水数字孪生层、仿真指标、GeoJSON；
- 实时 Agent 地理编码、天气上下文、风险筛查和失联降级；
- 雷达体素加载、synthetic 质量标记、集合短临和可视化；
- 天气解析、模型和服务 smoke；
- 数据契约与回放。

### 10.2 演示风险研究分割

产物：`artifacts/reports/research_metrics.json`

```text
model_version: rf-risk-conformal-v1
train_event: demo-2024-0712
calibration_event: demo-2024-0819
test_event: demo-2024-0905
train_rows: 72
calibration_rows: 72
test_rows: 72
coverage_target: 0.90
calibration_radius: 0.07375900243554494
```

测试结果：

```text
MAE                 0.03745071396971673
RMSE                0.05174230581276359
AUC                 0.9935064935064936
F1                  0.9438202247191011
Brier               0.09717846835443535
Top-K hit rate      1.0
Interval coverage   0.8055555555555556
Mean interval width 0.14369515074055425
```

解释：这三事件是固定种子的合成演示数据，结果证明风险模型、校准接口和评测脚本连通，不代表真实城市泛化。

### 10.3 UrbanFlood24 Lite HGB

实验协议：

```text
fit events: 22
calibration events: 2
test events: 12
rows_fit: 249986
forecast horizon: 10 minutes
coverage target: 0.90
```

总体结果来自 `artifacts/reports/urbanflood_lite_metrics.json`：

```text
MAE                 0.00238593 m
RMSE                0.01167710 m
R2                  0.987339
CSI @ 0.01 m        0.89593（以报告聚合值为准）
CSI @ 0.05 m        0.91263
CSI @ 0.10 m        0.92057
90% coverage        0.917384
```

README 中保留的四舍五入结果是可引用版本；正式论文应直接读取 JSON，避免手工抄写造成差异。

### 10.4 GPU ConvGRU

已保存报告：`artifacts/convgru_urbanflood.json`

```text
device: cuda
gpu: NVIDIA GeForce RTX 4090 D
epochs: 4
fit_events: 21
validation_events: 3
test_events: 12
```

测试结果：

```text
MAE                  0.0037151253782212734 m
RMSE                 0.01755915768444538 m
R2                   0.9857076406478882
CSI @ 0.01 m         0.8955923004314995
CSI @ 0.05 m         0.9125036712679893
CSI @ 0.10 m         0.9117805860653726
```

权重和报告 SHA-256：

```text
artifacts/convgru_urbanflood.json
c22c43d6f2e151a33bd8b57d2cebd636761671dcd95e913176200aec62a27277

artifacts/convgru_urbanflood.pt
7b7377c224f9d340e5c28834a004868cbadd9be1a188ce4181f7755e533dfbc4
```

解释：这是一次 RTX 4090 D、4 轮、单种子可复现快照。脚本默认完整训练 12 轮，但报告中的 4 轮结果不能包装成完整消融或生产准确率。

### 10.5 结果定义

连续误差：

\[
MAE=\frac{1}{n}\sum_i|y_i-\hat y_i|
\]

\[
RMSE=\sqrt{\frac{1}{n}\sum_i(y_i-\hat y_i)^2}
\]

阈值 CSI：

\[
CSI=\frac{TP}{TP+FP+FN}
\]

概率指标：

- AUC：按 risk probability 对二分类标签排序的 ROC 面积；
- F1：二值化预测与二值化标签的调和平均；
- Brier：二元概率预测的均方误差；
- Top-K hit rate：预测概率最高 K 个对象中标签超过阈值的比例；
- interval coverage：真实值落在 `[lower, upper]` 的比例；
- interval width：区间平均宽度。

所有阈值必须写入报告：例如 `0.01/0.05/0.10m` 或风险分类阈值 `0.5`，不能只报告一个没有单位的“准确率”。

---

## 11. 实验设计和消融

### 11.1 严格事件级划分

禁止：

```text
把同一场暴雨的相邻时间片随机拆到 train/test
```

正确：

```text
完整暴雨事件 → fit
完整暴雨事件 → calibration/validation
完整暴雨事件 → test
```

报告必须同时列出事件 ID，不能只列样本行数。

### 11.2 消融矩阵

| 实验 | 组件 | 研究问题 |
|---|---|---|
| A | 持续性基线 | 模型是否超过当前状态延续 |
| B | 仅降雨 | 气象输入本身提供多少信息 |
| C | 降雨 + 地形/下垫面 | 静态环境是否帮助尺度落地 |
| D | 降雨 + 雷达体素 | 对流结构是否帮助短临 |
| E | 加排水压力 | 物理约束是否改善异常区域 |
| F | 加分裂校准 | 区间覆盖是否接近目标 |
| G | 完整行动闭环 | 风险是否转化为更低暴露 |

### 11.3 最低实验记录

每次实验至少保存：

```json
{
  "git_commit": "866e597...",
  "data_manifest_sha256": "...",
  "config_sha256": "...",
  "seed": 7,
  "fit_events": ["..."],
  "calibration_events": ["..."],
  "test_events": ["..."],
  "feature_names": ["..."],
  "model_name": "...",
  "model_params": {},
  "metrics": {},
  "runtime_seconds": 0,
  "device": "cpu/cuda",
  "source_status": {}
}
```

### 11.4 后续科研实验

在获得授权的真实数据后，补充：

1. 三个以上随机种子；
2. bootstrap 或 95% 置信区间；
3. location leave-one-out；
4. 不同暴雨强度和持续时间分层；
5. 缺测、缓存和延迟敏感性；
6. 模型推理延迟、显存和 CPU 降级延迟；
7. 应急专家盲评；
8. 固定阈值与风险感知行动策略的 ARU 对比。

---

## 12. 报告和图表生成

建议图表及来源：

```text
artifacts/figures/
  urbanflood_*.html/png       UrbanFlood 指标和事件图
  research_*.html/png         演示风险模型指标
  radar_*.html                雷达体素和运动矢量
  drainage_*.geojson/html     排水图层与压力结果
```

每张图都必须放置：

- 数据集名称；
- 事件或时间范围；
- 空间分辨率；
- 时间步长；
- 单位；
- 数据性质；
- 模型版本；
- 是否使用缓存或合成数据。

图标题示例：

```text
UrbanFlood24 Lite 测试事件平均 CSI
数据性质：水动力模拟数据；预测步长：10 min；模型：HGB residual baseline；split：event-level
```

禁止标题：

```text
长春实时积水准确率
```

除非图中确实使用了授权的长春实时积水观测，并记录了可审计的测试事件。

---

## 13. 端到端复现清单

### A. 代码和环境

```bash
git clone https://github.com/Oookla28/tianheng-weather-risk.git
cd tianheng-weather-risk
# 如果复现本地完整研究包，切换到明确的 commit 866e597...
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### B. 基础验证

```bash
python -m pytest -q
python -m compileall -q app.py
```

期望：

```text
10 passed
无 compileall 报错
```

### C. 演示数据和风险模型

```bash
python3 scripts/prepare_demo.py
python3 scripts/train_demo.py
python3 scripts/evaluate_demo.py
python3 scripts/train_research.py
python3 scripts/evaluate_research.py
```

核对：

```bash
cat artifacts/reports/research_split.json
cat artifacts/reports/research_metrics.json
```

### D. UrbanFlood Lite

```bash
# 确认 raw archive SHA-256 后解压到 Lite 目录
python3 scripts/train_urbanflood_lite.py \\
  --data-root data/external/urbanflood24_lite \\
  --max-train-rows 250000 \\
  --max-iter 160
```

核对：

```bash
python3 - <<'PY'
import json
m=json.load(open('artifacts/reports/urbanflood_lite_metrics.json'))
print(m['dataset'])
print(len(m['train_events']), len(m['calibration_events']), len(m['test_events']))
print(m['aggregate'])
PY
```

### E. GPU ConvGRU

```bash
python3 scripts/train_convgru_urbanflood.py \\
  --data-root data/external/urbanflood24_lite \\
  --seq-len 6 --epochs 4 --batch-size 4 --hidden 16 --seed 7 \\
  --output-prefix artifacts/convgru_smoke
```

确认输出中：

```text
device
cuda
gpu
fit_events
validation_events
test_events
test.mae_m
```

生产式研究跑法：

```bash
python3 scripts/train_convgru_urbanflood.py \\
  --data-root data/external/urbanflood24_lite \\
  --seq-len 6 --epochs 12 --batch-size 2 --hidden 32 --lr 2e-3 --seed 7 \\
  --output-prefix artifacts/convgru_urbanflood_repro
```

### F. 实时天气 smoke

```bash
python3 - <<'PY'
from src.live_agent import fetch_live_context, assess_live_risk
context = fetch_live_context("长春", use_cache=False)
result = assess_live_risk(context)
print(context["location"])
print(context["provenance"])
print(result["risk_level"], result["severe_weather_probability"])
print(result["probability_status"])
PY
```

网络失败时应看到：

```text
cache_status=stale 或 unavailable
steps 中包含 forecast.fallback
```

此时不能把结果标成实时观测。

### G. 雷达和排水 smoke

```bash
python3 - <<'PY'
from src.radar_nowcast import RadarVolumeAdapter
from src.drainage_twin import build_demo_twin

radar = RadarVolumeAdapter().load()
nowcast = RadarVolumeAdapter().nowcast(radar)
print(radar.source, radar.shape, sorted(nowcast))

twin = build_demo_twin(seed=42, n=6)
print(twin.summary(1.0, 60))
print(list(twin.simulation_geojson(1.0, 60)))
PY
```

如果没有 `data/radar/volume*.npz`，必须输出 `synthetic` 和 `synthetic_demo` 标记。

---

## 14. 故障排查

### 14.1 `UrbanFlood24 Lite not found`

原因：原始数据未下载、目录名错误或被 `.gitignore` 排除。

处理：

```bash
ls data/external/urbanflood24_lite/train/flood
ls data/external/urbanflood24_lite/test/flood
```

确认 `location*/r*/flood.npy` 存在，然后重新传入 `--data-root`。

### 14.2 `PyTorch is required`

原因：只安装了 CPU requirements，没有安装 `requirements-gpu.txt`。

处理：

```bash
python -m pip install -r requirements-gpu.txt
```

再检查 CUDA 和显卡驱动。

### 14.3 GPU 运行速度异常

记录：

```text
torch version
CUDA availability
GPU name
batch size
hidden
workers
```

先使用 `--epochs 4 --batch-size 4 --hidden 16` 做 smoke，再使用正式参数。不要把 smoke 结果与 12 轮结果混为一谈。

### 14.4 地理编码返回错误长春

代码对“长春/长春市”自动使用 `Changchun` 查询，并优先选择吉林行政区。如果直接传坐标，使用：

```python
fetch_live_context(lat=43.88, lon=125.32)
```

### 14.5 雷达被标记为 synthetic

检查：

```bash
find data/radar -maxdepth 1 -name 'volume*.npz'
```

没有文件时这是预期行为。不要删除 `quality_flags` 来掩盖数据缺失。

### 14.6 公开仓库无法直接重跑外部数据

这是设计上的许可和体积边界。使用 manifest 重新下载原始数据；公开仓库的代码、报告、测试和配置可以先完成 R0/R1 复现。

### 14.7 文档命令过时

以实际脚本名为准：

```text
正确：scripts/train_convgru_urbanflood.py
错误：scripts/train_spatiotemporal.py
```

以 `python3.11` 为准，不假设系统存在名为 `python` 的命令。

---

## 15. 论文写作对应

### 15.1 引言

说明气象网格到城市对象的尺度鸿沟、积水标签稀缺和行动资源约束。

### 15.2 数据与问题定义

列出事件、时间步、网格、目标变量、数据质量和授权边界。

### 15.3 方法

按以下顺序写：

1. 特征契约与事件级切分；
2. HGB residual baseline；
3. ConvGRU 空间—时间编码器；
4. 分裂校准区间；
5. 风险对象和关键性；
6. 排水孪生与反事实；
7. 资源约束行动规划；
8. 来源状态与证据链。

### 15.4 实验

必须分开报告：

- 演示风险模型：3 个合成事件；
- UrbanFlood24 Lite：公开模拟数据，12 个测试事件；
- GPU ConvGRU：RTX 4090 D，4 轮 checked snapshot；
- 真实 CMA/长春：授权后再报告，不用模拟数据代替。

### 15.5 局限

明确写出：

- UrbanFlood24 是模拟标签；
- GPU 单种子、4 轮结果只是链路验证；
- HGB 与 ConvGRU 的事件划分不同，不能直接进行不公平比较；
- 评测目前是一部预测或一步水深增量，不能直接外推至多小时积水全过程；
- 排水 twin 是筛查模型，不是水力认证；
- 实时天气是模型网格和服务接口，不等价于地面站或雷达真值；
- 真实 CMA 和长春排水接口仍需授权和现场校准。

---

## 16. 公开材料与隐私边界

公开仓库可以包含：

- 后端源代码；
- 不含密钥的配置模板；
- 测试；
- 公开数据 manifest；
- 论文方法和公开结果；
- 不含敏感信息的架构说明。

不要公开：

- API token、SSH 密码、私钥；
- 未授权 CMA 原始产品；
- 长春市政内部管网、泵站或监控导出；
- 真实用户位置和现场数据；
- GPU 服务器连接信息；
- 未经许可的外部数据完整压缩包；
- 内部答辩材料中未公开的个人信息。

---

## 17. 最终复现验收表

| 项目 | 验收命令/文件 | 通过标准 |
|---|---|---|
| Python | `python3.11 --version` | >=3.11 |
| 依赖 | `pip install -r requirements.txt` | 无安装错误 |
| 单元测试 | `python -m pytest -q` | 10 passed |
| 编译 | `python -m compileall -q app.py` | 无错误 |
| 演示数据 | `scripts/prepare_demo.py` | processed 表生成 |
| 风险研究 | train/evaluate research | JSON/CSV 生成 |
| UrbanFlood | HGB script | Lite metrics JSON/CSV |
| GPU | ConvGRU script | pt/json 生成，GPU 字段正确 |
| 雷达 | `RadarVolumeAdapter().load()` | source 和 quality_flags 正确 |
| 排水 | `DrainageTwin.summary()` | 数值和图层可序列化 |
| 实时 Agent | `fetch_live_context` | live/cache/unavailable 状态明确 |
| 证据链 | `research_split.json` | event/model/data/coverage 字段完整 |
| 许可 | manifest/README | 来源、哈希和限制清楚 |

最低可发表证据：

1. 固定 commit；
2. 固定数据 manifest 和哈希；
3. 完整事件划分；
4. 至少一个持续性基线；
5. 至少三个随机种子或明确说明单种子限制；
6. 报告连续误差、事件识别和区间覆盖；
7. 保存原始 JSON/CSV 指标，不只放截图；
8. 说明模拟、合成、缓存和真实数据的边界；
9. 提供失败回退和数据质量验证；
10. 不把演示效果写成生产准确率。

---

## 18. 结论性陈述

天衡的算法内核不是一个天气页面，而是一条可复现的风险到行动链：

```text
天气/雷达/城市状态
    → 统一数据契约与来源标记
    → 时空特征和环境约束
    → HGB/ConvGRU 影响预测
    → 分裂校准和风险区间
    → 关键设施暴露排序
    → 排水压力与反事实推演
    → 资源约束行动规划
    → 可审计证据和报告
```

在当前本地完整研究包中，演示风险模型、UrbanFlood24 Lite HGB 路径、GPU ConvGRU 路径、实时天气 Agent、雷达体素基线和排水数字孪生已经形成可运行链路。公开仓库提供后端接口和适配器边界。真正的业务实时化仍需要授权 CMA 产品、长春城市排水观测、事件级实测标签、持续校准和人工值守；这不是报告的缺陷，而是科研原型进入业务系统必须显式解决的验证条件。
