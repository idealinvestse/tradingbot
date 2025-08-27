from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from pydantic import BaseModel, Field, HttpUrl


class NewsItem(BaseModel):
    title: str
    url: HttpUrl | None = None
    source: str
    symbols: list[str] = []  # e.g., ["BTC", "ETH", "BTCUSDT"]
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NewsSnapshot(BaseModel):
    at: datetime
    items: list[NewsItem]


class BaseNewsProvider(ABC):
    @abstractmethod
    def get_latest(self, symbols: list[str], since: datetime | None = None) -> list[NewsItem]:
        """Fetch latest news for given symbols since optional timestamp (UTC)."""
        raise NotImplementedError

    def snapshot(self, symbols: list[str], since: datetime | None = None) -> NewsSnapshot:
        now = datetime.now(timezone.utc)
        return NewsSnapshot(at=now, items=self.get_latest(symbols, since))
