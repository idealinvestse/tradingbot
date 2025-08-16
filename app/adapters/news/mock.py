from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import List, Optional

from .base import BaseNewsProvider, NewsItem


class MockNewsProvider(BaseNewsProvider):
    """Mock news provider.

    Deterministic pseudo-news generated per-hour per-symbol for reproducible tests.
    """

    def get_latest(self, symbols: List[str], since: Optional[datetime] = None) -> List[NewsItem]:
        now = datetime.now(timezone.utc)
        hour = (since or now).replace(minute=0, second=0, microsecond=0)
        items: List[NewsItem] = []
        for sym in symbols:
            # Generate one item per symbol per hour window
            h = hash((sym, hour.isoformat()))
            title = f"Mock headline for {sym} @ {hour.isoformat()}"
            items.append(
                NewsItem(
                    title=title,
                    url=None,
                    source="MockNewsProvider",
                    symbols=[sym],
                    published_at=hour + timedelta(minutes=5 + (h % 20)),
                )
            )
        return items
