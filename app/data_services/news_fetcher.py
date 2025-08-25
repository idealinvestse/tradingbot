import abc
import datetime
import logging
from typing import List

from app.data_services.models import NewsArticle

logger = logging.getLogger(__name__)


class BaseNewsFetcher(abc.ABC):
    """
    Abstract base class for news fetching services.
    """

    @abc.abstractmethod
    def fetch_news(self, symbols: List[str], since: datetime.datetime, until: datetime.datetime) -> List[NewsArticle]:
        """
        Fetches news articles for a given list of symbols within a time range.

        :param symbols: List of asset symbols (e.g., ['BTC/USDT', 'ETH/USDT']).
        :param since: The start of the time range (inclusive).
        :param until: The end of the time range (exclusive).
        :return: A list of NewsArticle objects.
        """
        raise NotImplementedError


class DemoNewsFetcher(BaseNewsFetcher):
    """
    A demonstration news fetcher that returns static, hardcoded news articles.
    Useful for development and testing without requiring an API key.
    """

    def fetch_news(self, symbols: List[str], since: datetime.datetime, until: datetime.datetime) -> List[NewsArticle]:
        """
        Returns a list of dummy news articles for the requested symbols.
        """
        logger.info(
            f"Fetching demo news for symbols: {symbols} from {since} to {until}"
        )

        # Create a sample of articles that could match the request
        all_articles = [
            NewsArticle(
                source="CryptoNews",
                headline="Bitcoin Surges Past $80,000 in Historic Rally",
                url="https://example.com/btc-rally",
                published_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
                symbols=["BTC/USDT", "BTC/EUR"],
                summary="Bitcoin (BTC) has reached a new all-time high, driven by institutional adoption.",
            ),
            NewsArticle(
                source="TechChronicle",
                headline="Ethereum 2.0 Upgrade Nears Completion, Boosting Investor Confidence",
                url="https://example.com/eth-upgrade",
                published_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2),
                symbols=["ETH/USDT"],
                summary="The final phase of the Ethereum 2.0 rollout is expected to significantly reduce gas fees.",
            ),
            NewsArticle(
                source="MarketWatch",
                headline="Regulatory Uncertainty Clouds Crypto Market Outlook",
                url="https://example.com/crypto-regs",
                published_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1),
                symbols=["BTC/USDT", "ETH/USDT", "XRP/USDT"],
                summary="Analysts are divided on the impact of upcoming regulations on the broader crypto market.",
            ),
        ]

        # Filter articles based on the requested symbols
        fetched_articles = [
            article
            for article in all_articles
            if any(symbol in article.symbols for symbol in symbols)
        ]

        logger.debug(f"Found {len(fetched_articles)} demo articles matching the criteria.")
        return fetched_articles
