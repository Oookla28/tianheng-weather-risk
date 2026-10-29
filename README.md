# 天衡 Tianheng

面向粗分辨率气象数据与稀缺城市灾害标签的暴雨影响预报与不确定性决策系统。

本仓库是竞赛可演示的离线 MVP。它用确定性演示事件保证无外网也能启动，同时为 GPM IMERG、ERA5、CMA 站点和城市 GIS 数据预留适配器。系统输出对象级风险排序和资源调度建议，不把粗分辨率降水数据表述为街道级精确降雨或积水深度预测。

## 能做什么

- 回放历史或演示暴雨事件，按时间滑块查看降雨和风险演化；
- 对道路、医院、学校进行对象级风险排序，并展示风险原因和置信度；
- 在资源、时间和道路约束下生成巡检、排水和封路方案；
- 比较“不行动”和“提前行动”的关键设施暴露、巡检距离和响应时间；
- 查看数据来源、标签质量、模型版本、规则依据和人工确认状态；
- 运行基线、消融、跨事件评估和科研报告导出。

## 快速启动

Windows PowerShell：

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python scripts\\prepare_demo.py
streamlit run app.py
```

浏览器打开 `http://localhost:8501`。若尚未安装脚本目录，直接启动 `app.py` 会自动创建演示数据。

Docker：

```powershell
docker compose up --build
```

常用命令：

```text
make prepare      生成确定性演示事件和数据
make train        训练基线和风险模型
make evaluate     生成评测结果
make replay       执行命令行事件回放
make run          启动 Streamlit
make test         运行冒烟测试
```

Windows 没有 Make 时，直接运行对应的 `python scripts\\*.py` 命令即可。

## 总体架构

```text
数据源/演示数据
  -> 数据登记、质控、时间空间统一
  -> 特征和标签层
  -> 降雨时间序列模型 + 地形静态分支 + 对象关系图
  -> 风险概率和 P10/P50/P90 不确定性
  -> OR-Tools/规则兜底行动优化
  -> Streamlit 地图、回放、反事实对比和证据链
  -> 事件复盘、科研评测和论文图表
```

首版使用模块化单体，数据落地为 Parquet/SQLite，模型由 Python 调用。稳定后可拆分为 FastAPI、PostGIS、异步 worker 和对象存储。全链路以 `event_id`、`run_id`、`data_version`、`model_version` 和 `created_at` 追踪。

## 科研主线

论文主线是：在降水分辨率较粗、城市灾害标签稀缺的条件下，融合地形易涝性和道路/设施关系，能否提升对象风险排序，并通过不确定性校准改善行动方案。

建议实验顺序：

1. 持续性预测或规则基线；
2. LightGBM/MLP 或 Temporal CNN/ConvLSTM；
3. 加入 DEM、坡度、汇流和土地覆盖；
4. 加入道路、医院、学校关系图；
5. 加入弱标签和少量人工标签；
6. 加入区间校准；
7. 比较阈值规则、贪心调度和风险感知优化。

实验必须按完整暴雨事件划分训练、验证和测试，禁止把相邻时间片随机拆分造成泄漏。报告 MAE、RMSE、CSI、POD、FAR、AUC、F1、Brier、Top-K 命中率、Coverage、关键设施覆盖率、响应时间和资源成本。建议使用至少3个随机种子并报告95%置信区间。

## 数据适配

### 演示数据

`src/demo_data.py` 生成确定性事件、网格、道路、医院和学校，便于无网络演示和端到端测试。演示数据会标注为 `label_quality=synthetic`，不用于宣称真实业务效果。

### 真实数据适配器

- GPM IMERG：半小时降水，用于历史回放和低延迟模拟；
- ERA5/ERA5-Land：小时背景场、累计降水和陆面特征；
- CMA 地面站/雷达：有授权后接入，作为中国区域增强数据；
- SRTM 或其他 DEM：高程、坡度、汇流和洼地特征；
- OpenStreetMap：道路、医院、学校和水系，发布时注明 OSM 贡献者并遵守 ODbL；
- 城市积水、道路中断和应急记录：用于真实监督标签。

每个数据对象需要保存 `source`、`license`、`spatial_resolution`、`temporal_resolution`、`version` 和 `label_quality`。没有真实标签时，只输出风险排序，并在报告中说明弱标签来源和局限。

## 目录结构

```text
app.py
src/
  schemas.py       数据契约和版本字段
  demo_data.py     确定性演示数据
  features.py      网格和对象特征
  models.py        基线、风险模型和不确定性
  risk.py          风险排序和证据生成
  optimize.py      资源约束行动方案
  evaluation.py    指标和事件级评估
  service.py       端到端服务编排
  ui.py            Streamlit 组件
scripts/
  prepare_demo.py
  train_demo.py
  evaluate_demo.py
  replay_demo.py
data/
  raw/ interim/ processed/ external/
artifacts/
  models/ figures/ reports/
tests/
```

## 演示脚本

1. 选择一场暴雨事件；
2. 将时间滑块切换到 T-120、T-60、T-30；
3. 查看降雨趋势和风险网格；
4. 点击道路、医院或学校查看风险原因；
5. 生成巡检、排水、封路方案；
6. 对比提前行动和不行动的影响；
7. 查看模型版本、数据来源和规则依据；
8. 导出事件复盘报告。

## 竞赛评分映射

| 评分项 | 本仓库中的证据 |
|---|---|
| 创新性 | 跨分辨率影响预报、稀缺标签学习、不确定性决策、风险到行动闭环 |
| 需求分析 | 事件复盘、需求矩阵、道路/医院/学校对象化输出 |
| AI技术应用 | 时空模型、静态特征分支、图聚合、区间校准、约束优化 |
| 项目实施 | 模块化单体、数据版本、降级路径、Docker和一键回放 |
| 应用成效 | 风险命中、关键设施覆盖、提前量、暴露降低、响应时间和专家盲评 |
| 总结展望 | 数据适配器、风险插件和行动插件可迁移到其他城市和灾种 |

## 当前版本边界

演示版本的目标是可运行和可复现。生产级实时预警还需要真实部门数据授权、持续在线校准、正式积水标签、人工值守和安全审查。任何使用合成或弱标签得到的结果都会在界面和报告中明确标注。
