from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ParameterInfo(BaseModel):
    type: str
    default: Any | None = None


class RiskInfo(BaseModel):
    minimal_roi: dict[str, float] | None = None
    stoploss: float | None = None
    trailing_stop: bool | None = None


class PerformanceInfo(BaseModel):
    last_backtest: Any | None = None


class StrategySpec(BaseModel):
    id: str
    name: str
    class_name: str
    file_path: str
    status: str
    timeframes: list[str] = Field(default_factory=list)
    markets: list[str] = Field(default_factory=list)
    indicators: list[str] = Field(default_factory=list)
    parameters: dict[str, ParameterInfo] = Field(default_factory=dict)
    risk: RiskInfo = Field(default_factory=RiskInfo)
    performance: PerformanceInfo = Field(default_factory=PerformanceInfo)
    tags: list[str] = Field(default_factory=list)


class MethodSpec(BaseModel):
    id: str
    name: str
    category: str
    description: str
    related_strategies: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class ConceptSpec(BaseModel):
    id: str
    name: str
    description: str
    references: list[str] = Field(default_factory=list)


class SourceSpec(BaseModel):
    id: str
    title: str
    path: str
    topic: str
    quality: str


class RegistrySchema(BaseModel):
    version: int
    updated_utc: str
    strategies: list[StrategySpec] = Field(default_factory=list)
    methods: list[MethodSpec] = Field(default_factory=list)
    concepts: list[ConceptSpec] = Field(default_factory=list)
    sources: list[SourceSpec] = Field(default_factory=list)
