from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

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
    timeframes: list[str] = field(default_factory=list)
    markets: list[str] = field(default_factory=list)
    indicators: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    risk: dict[str, Any] = field(default_factory=dict)
    performance: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MethodSpec:
    id: str
    name: str
    category: str
    description: str = ""
    related_strategies: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConceptSpec:
    id: str
    name: str
    description: str = ""
    references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceSpec:
    id: str
    title: str
    path: str
    topic: str = ""
    quality: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- Ideation and experiment models ---


@dataclass
class Idea:
    id: str
    title: str
    description: str
    status: str = "proposed"  # proposed|in_progress|accepted|rejected|parked
    tags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    owner: str | None = None
    created_utc: str = field(default_factory=utcnow_iso)


@dataclass
class Experiment:
    id: str
    idea_id: str
    strategy_id: str
    hypothesis: str
    timeframe: str
    markets: list[str]
    period_start_utc: str
    period_end_utc: str
    seed: int | None = None
    config_hash: str | None = None
    created_utc: str = field(default_factory=utcnow_iso)


@dataclass
class Run:
    id: str
    experiment_id: str
    kind: str  # backtest|hyperopt|paper|live
    started_utc: str
    finished_utc: str | None = None
    status: str = "running"  # running|completed|failed
    docker_image: str | None = None
    freqtrade_version: str | None = None
    config_json: str | None = None
    data_window: str | None = None
    artifacts_path: str | None = None


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
    sha256: str | None = None


@dataclass
class Decision:
    id: str
    idea_id: str
    decision: str  # promote|reject|park
    rationale: str
    decided_utc: str = field(default_factory=utcnow_iso)
    approver: str | None = None


@dataclass
class Incident:
    id: str
    run_id: str
    severity: str
    description: str
    log_excerpt_path: str | None = None
    created_utc: str = field(default_factory=utcnow_iso)
