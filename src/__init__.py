"""天衡 Tianheng —— 面向粗分辨率气象数据与稀缺标签的城市暴雨影响预报与不确定性决策系统.

顶层包只暴露版本号与项目根路径，其余能力按科研/工程分层组织：

    common     配置、契约、版本、IO
    ingest     数据接入（合成基准 + 真实数据适配器占位）
    preprocess 网格、地形派生、弱标签、事件级划分
    features   网格/对象/图特征
    models     降雨临近预报、风险模型、概率校准
    risk       风险打分、级联传播、可读依据
    optimize   行动优化、方案校验、反事实推演
    agent      本地预案知识库、模板化证据解释
    evaluation 指标、基准评测、消融实验、行动效用
    api        接口契约（Streamlit 直调 + 可选 ASGI）
    ui         Streamlit 页面组件
"""

from __future__ import annotations

from pathlib import Path

__version__ = "0.2.0"
__project_name__ = "天衡 Tianheng"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"
ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
DOCS_DIR = PROJECT_ROOT / "docs"

__all__ = [
    "__version__",
    "__project_name__",
    "PROJECT_ROOT",
    "CONFIG_DIR",
    "DATA_DIR",
    "ARTIFACT_DIR",
    "DOCS_DIR",
]
