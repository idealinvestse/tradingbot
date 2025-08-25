import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class NewsArticle:
    """
    Represents a single news article fetched from an external source.
    """
    source: str
    headline: str
    url: str
    published_at: datetime.datetime
    symbols: list[str]
    summary: Optional[str] = None
    content: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
