import abc
import logging

from app.data_services.models import NewsArticle

logger = logging.getLogger(__name__)


class BaseSentimentAnalyzer(abc.ABC):
    """
    Abstract base class for sentiment analysis services.
    """

    @abc.abstractmethod
    def analyze(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        """
        Analyzes a list of news articles and enriches them with sentiment data.

        :param articles: A list of NewsArticle objects to analyze.
        :return: The same list of articles, with sentiment_score and sentiment_label populated.
        """
        raise NotImplementedError


class DemoSentimentAnalyzer(BaseSentimentAnalyzer):
    """
    A demonstration sentiment analyzer that uses simple keyword matching.
    """

    POSITIVE_KEYWORDS = ["surges", "historic rally", "all-time high", "upgrade", "confidence", "adoption"]
    NEGATIVE_KEYWORDS = ["uncertainty", "clouds", "regulatory", "divided", "impact"]

    def analyze(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        """
        Analyzes articles based on the presence of positive or negative keywords.
        """
        logger.info(f"Analyzing sentiment for {len(articles)} articles.")

        for article in articles:
            text_to_analyze = (article.headline + " " + (article.summary or "")).lower()

            score = 0.0
            pos_count = sum(1 for keyword in self.POSITIVE_KEYWORDS if keyword in text_to_analyze)
            neg_count = sum(1 for keyword in self.NEGATIVE_KEYWORDS if keyword in text_to_analyze)

            if pos_count > neg_count:
                score = 0.75
                label = "positive"
            elif neg_count > pos_count:
                score = -0.75
                label = "negative"
            else:
                score = 0.0
                label = "neutral"

            article.sentiment_score = score
            article.sentiment_label = label
            logger.debug(
                f'Analyzed headline "{article.headline[:30]}...": '
                f'Score={article.sentiment_score}, Label={article.sentiment_label}'
            )

        return articles
