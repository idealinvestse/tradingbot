from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, HttpUrl, Field


class NewsItem(BaseModel):
    title: str
    url: Optional[HttpUrl] = None
    source: str
    symbols: List[str] = []  # e.g., ["BTC", "ETH", "BTCUSDT"]
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NewsSnapshot(BaseModel):
    at: datetime
    items: List[NewsItem]


class BaseNewsProvider(ABC):
    @abstractmethod
    def get_latest(self, symbols: List[str], since: Optional[datetime] = None) -> List[NewsItem]:
        """Fetch latest news for given symbols since optional timestamp (UTC)."""
        raise NotImplementedError

    def snapshot(self, symbols: List[str], since: Optional[datetime] = None) -> NewsSnapshot:
        now = datetime.now(timezone.utc)
        return NewsSnapshot(at=now, items=self.get_latest(symbols, since))
