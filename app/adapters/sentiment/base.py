from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class SentimentItem(BaseModel):
    pair: str
    score: float = Field(ge=-1.0, le=1.0)
    source: str
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SentimentSnapshot(BaseModel):
    at: datetime
    items: list[SentimentItem]


class BaseSentimentProvider(ABC):
    @abstractmethod
    def get_score(self, pair: str, at: datetime | None = None) -> float:
        """Return a normalized sentiment score in [-1, 1] for a specific pair at time 'at' (UTC)."""

    def get_snapshot(self, pairs: list[str], at: datetime | None = None) -> SentimentSnapshot:
        at = at or datetime.now(timezone.utc)
        items = [SentimentItem(pair=p, score=float(self.get_score(p, at)), source=self.__class__.__name__, at=at) for p in pairs]
        return SentimentSnapshot(at=at, items=items)
