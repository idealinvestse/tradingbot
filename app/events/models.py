from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class Impact(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Event(BaseModel):
    name: str
    symbols: List[str] = Field(default_factory=list)  # e.g., ["BTC", "ETH", "BTCUSDT"]
    category: str = "general"  # e.g., protocol, macro, exchange, product
    impact: Impact = Impact.medium
    start: datetime
    end: Optional[datetime] = None
    description: Optional[str] = None

    @validator("end")
    def validate_range(cls, v, values):  # type: ignore[override]
        start = values.get("start")
        if v and start and v < start:
            raise ValueError("end must be >= start")
        return v


class EventSchedule(BaseModel):
    events: List[Event] = Field(default_factory=list)
