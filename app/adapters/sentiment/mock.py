from __future__ import annotations

from datetime import datetime, timezone

from .base import BaseSentimentProvider


class MockSentimentProvider(BaseSentimentProvider):
    """Mock provider returning a neutral-to-slightly-randomized score.

    Deterministic by hour to keep backtests reproducible without external I/O.
    """

    def get_score(self, pair: str, at: datetime | None = None) -> float:
        at = at or datetime.now(timezone.utc)
        # Simple deterministic hash based on hour and pair length
        h = (hash((pair, at.replace(minute=0, second=0, microsecond=0).isoformat())) % 1000) / 1000.0
        # map [0,1] -> [-0.2, 0.2]
        return (h - 0.5) * 0.4
