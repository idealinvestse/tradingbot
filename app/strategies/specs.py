from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


UTC = timezone.utc


def utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


# --- Registry core models ---

@dataclass
class StrategySpec:
    id: str
    name: str
    class_name: str
    file_path: str
    status: str = "draft"
    timeframes: List[str] = field(default_factory=list)
    markets: List[str] = field(default_factory=list)
    indicators: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    risk: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MethodSpec:
    id: str
    name: str
    category: str
    description: str = ""
    related_strategies: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConceptSpec:
    id: str
    name: str
    description: str = ""
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourceSpec:
    id: str
    title: str
    path: str
    topic: str = ""
    quality: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --- Ideation and experiment models ---

@dataclass
class Idea:
    id: str
    title: str
    description: str
    status: str = "proposed"  # proposed|in_progress|accepted|rejected|parked
    tags: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    owner: Optional[str] = None
    created_utc: str = field(default_factory=utcnow_iso)


@dataclass
class Experiment:
    id: str
    idea_id: str
    strategy_id: str
    hypothesis: str
    timeframe: str
    markets: List[str]
    period_start_utc: str
    period_end_utc: str
    seed: Optional[int] = None
    config_hash: Optional[str] = None
    created_utc: str = field(default_factory=utcnow_iso)


@dataclass
class Run:
    id: str
    experiment_id: str
    kind: str  # backtest|hyperopt|paper|live
    started_utc: str
    finished_utc: Optional[str] = None
    status: str = "running"  # running|completed|failed
    docker_image: Optional[str] = None
    freqtrade_version: Optional[str] = None
    config_json: Optional[str] = None
    data_window: Optional[str] = None
    artifacts_path: Optional[str] = None


@dataclass
class Metric:
    run_id: str
    key: str
    value: float


@dataclass
class Artifact:
    run_id: str
    name: str
    path: str
    sha256: Optional[str] = None


@dataclass
class Decision:
    id: str
    idea_id: str
    decision: str  # promote|reject|park
    rationale: str
    decided_utc: str = field(default_factory=utcnow_iso)
    approver: Optional[str] = None


@dataclass
class Incident:
    id: str
    run_id: str
    severity: str
    description: str
    log_excerpt_path: Optional[str] = None
    created_utc: str = field(default_factory=utcnow_iso)
