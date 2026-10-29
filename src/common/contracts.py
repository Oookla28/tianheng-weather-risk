"""跨层数据契约：数据登记、标签质量、预测、行动方案与证据链。

这些契约是答辩时"可追溯"能力的落点：任何一条预测或建议都必须能回答
"这份结论由哪份数据、哪个模型、哪个版本、哪条规则生成"。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ------------------------------------------------------------------ 标签质量

LABEL_QUALITY_ORDER = ("real", "verified", "crowdsourced", "weak", "synthetic")

LABEL_QUALITY_NOTES: Dict[str, str] = {
    "real": "部门正式观测记录（需授权）",
    "verified": "人工核实过的现场记录",
    "crowdsourced": "众包/新闻公开记录，未逐条核实",
    "weak": "由透明物理规则生成的弱标签",
    "synthetic": "合成基准数据，仅用于方法验证",
}


def normalize_label_quality(value: str) -> str:
    value = str(value).strip().lower()
    return value if value in LABEL_QUALITY_ORDER else "weak"


# ------------------------------------------------------------------ 数据登记

@dataclass
class DataRecord:
    """一份数据的登记信息（数据字典的最小实体）。"""

    name: str
    source: str
    license: str
    spatial_resolution: str
    temporal_resolution: str
    time_range: str
    version: str
    processing_version: str = "proc-v1"
    label_quality: str = "synthetic"
    variables: List[str] = field(default_factory=list)
    note: str = ""
    download_time: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ------------------------------------------------------------------ 运行元数据

@dataclass(frozen=True)
class RunMetadata:
    """所有预测与方案的统一主键。"""

    event_id: str
    run_id: str
    data_version: str = "demo-v1"
    model_version: str = "baseline-v1"
    rule_version: str = "risk-level-rules-v1"
    seed: int = 42
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ------------------------------------------------------------------ 行动与方案

ACTION_STATUS = ("PENDING_CONFIRMATION", "CONFIRMED", "REJECTED")


@dataclass
class Action:
    action_id: str
    action_type: str
    target_id: str
    target_type: str
    priority: int
    start_in_minutes: int
    resource_id: str
    reason: str
    confidence: float
    risk_p50: float = 0.0
    risk_p10: float = 0.0
    risk_p90: float = 0.0
    department: str = ""
    status: str = "PENDING_CONFIRMATION"
    rule_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Evidence:
    """一条证据：来源、规则、模型版本与置信度。"""

    kind: str
    source: str
    rule: str
    model_version: str
    confidence: float
    detail: str = ""
    kb_docs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActionPlan:
    plan_id: str
    event_id: str
    run_id: str
    strategy: str
    time_index: int
    actions: List[Action]
    objective_value: float
    constraints_passed: bool
    violations: List[str]
    evidence: List[Dict[str, Any]]
    resource_usage: Dict[str, int] = field(default_factory=dict)
    generated_seconds: float = 0.0
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "event_id": self.event_id,
            "run_id": self.run_id,
            "strategy": self.strategy,
            "time_index": self.time_index,
            "actions": [a.to_dict() for a in self.actions],
            "objective_value": self.objective_value,
            "constraints_passed": self.constraints_passed,
            "violations": self.violations,
            "evidence": self.evidence,
            "resource_usage": self.resource_usage,
            "generated_seconds": self.generated_seconds,
            "created_at": self.created_at,
        }

    def table(self) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self.actions]


# ------------------------------------------------------------------ 风险评估

RISK_FIELDS = (
    "risk_p10",
    "risk_p50",
    "risk_p90",
    "risk_probability",
    "risk_level",
    "confidence",
    "main_reasons",
)


@dataclass
class RiskAssessment:
    """单个对象的风险评估结果，包含区间与依据。"""

    object_id: str
    object_type: str
    name: str
    x: int
    y: int
    criticality: float
    risk_p10: float
    risk_p50: float
    risk_p90: float
    risk_level: str
    confidence: float
    main_reasons: str
    model_version: str
    label_quality: str = "weak"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def risk_probability(self) -> float:
        return self.risk_p50


__all__ = [
    "LABEL_QUALITY_ORDER",
    "LABEL_QUALITY_NOTES",
    "normalize_label_quality",
    "DataRecord",
    "RunMetadata",
    "Action",
    "ActionPlan",
    "ACTION_STATUS",
    "Evidence",
    "RiskAssessment",
    "RISK_FIELDS",
    "utc_now_iso",
]
