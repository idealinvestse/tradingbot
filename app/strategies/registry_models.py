from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParameterInfo(BaseModel):
    type: str
    default: Optional[Any] = None


class RiskInfo(BaseModel):
    minimal_roi: Optional[Dict[str, float]] = None
    stoploss: Optional[float] = None
    trailing_stop: Optional[bool] = None


class PerformanceInfo(BaseModel):
    last_backtest: Optional[Any] = None


class StrategySpec(BaseModel):
    id: str
    name: str
    class_name: str
    file_path: str
    status: str
    timeframes: List[str] = Field(default_factory=list)
    markets: List[str] = Field(default_factory=list)
    indicators: List[str] = Field(default_factory=list)
    parameters: Dict[str, ParameterInfo] = Field(default_factory=dict)
    risk: RiskInfo = Field(default_factory=RiskInfo)
    performance: PerformanceInfo = Field(default_factory=PerformanceInfo)
    tags: List[str] = Field(default_factory=list)


class MethodSpec(BaseModel):
    id: str
    name: str
    category: str
    description: str
    related_strategies: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)


class ConceptSpec(BaseModel):
    id: str
    name: str
    description: str
    references: List[str] = Field(default_factory=list)


class SourceSpec(BaseModel):
    id: str
    title: str
    path: str
    topic: str
    quality: str


class RegistrySchema(BaseModel):
    version: int
    updated_utc: str
    strategies: List[StrategySpec] = Field(default_factory=list)
    methods: List[MethodSpec] = Field(default_factory=list)
    concepts: List[ConceptSpec] = Field(default_factory=list)
    sources: List[SourceSpec] = Field(default_factory=list)
