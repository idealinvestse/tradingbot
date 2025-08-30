import datetime
from dataclasses import dataclass


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
    summary: str | None = None
    content: str | None = None
    sentiment_score: float | None = None
    sentiment_label: str | None = None
