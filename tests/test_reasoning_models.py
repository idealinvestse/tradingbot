# pragma pylint: disable=missing-docstring, protected-access

import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from app.reasoning.ml_model import PlaceholderMLModel
from app.reasoning.rule_based_model import RuleBasedModel
from app.strategies.persistence.sqlite import connect, ensure_schema, upsert_news_articles
from app.data_services.models import NewsArticle


class TestRuleBasedModel(unittest.TestCase):
    """Unit tests for the RuleBasedModel."""

    def setUp(self):
        """Set up an in-memory SQLite database for testing."""
        self.conn = sqlite3.connect(":memory:")
        ensure_schema(self.conn, with_extended=True)
        self.model = RuleBasedModel(self.conn)

    def tearDown(self):
        """Close the database connection."""
        self.conn.close()

    def _create_dummy_dataframe(self, crossover: bool) -> pd.DataFrame:
        """Creates a dummy dataframe with or without a MA crossover."""
        dates = pd.to_datetime(["2023-01-01 12:00", "2023-01-01 12:05"], utc=True)
        if crossover:
            # Fast MA crosses above Slow MA
            close_prices = [100, 105]
            fast_ma = [99, 106]
            slow_ma = [101, 104]
        else:
            # No crossover
            close_prices = [100, 95]
            fast_ma = [101, 94]
            slow_ma = [102, 96]
        
        df = pd.DataFrame({
            'date': dates,
            'close': close_prices,
        })
        # The model calculates indicators internally, so we don't need to mock them here.
        return df

    def test_decision_buy_on_crossover_and_positive_sentiment(self):
        """Test that a 'buy' decision is made with positive signals."""
        # 1. Prepare data: Positive sentiment news
        articles = [
            NewsArticle(
                source="test", headline="Good News", url="http://test.com/1",
                published_at=datetime.now(timezone.utc) - timedelta(hours=1),
                sentiment_score=0.8, sentiment_label="positive"
            )
        ]
        upsert_news_articles(self.conn, articles)

        # 2. Create dataframe with a crossover event
        df = self._create_dummy_dataframe(crossover=True)

        # 3. Get decision
        decision = self.model.decide(df, {})

        # 4. Assert
        self.assertEqual(decision.action, "buy")
        self.assertIn("confirmed by positive sentiment", decision.reason)

    def test_decision_hold_on_crossover_but_negative_sentiment(self):
        """Test that a 'hold' decision is made if sentiment is negative."""
        # 1. Prepare data: Negative sentiment news
        articles = [
            NewsArticle(
                source="test", headline="Bad News", url="http://test.com/1",
                published_at=datetime.now(timezone.utc) - timedelta(hours=1),
                sentiment_score=-0.8, sentiment_label="negative"
            )
        ]
        upsert_news_articles(self.conn, articles)

        # 2. Create dataframe with a crossover event
        df = self._create_dummy_dataframe(crossover=True)

        # 3. Get decision
        self.model.sentiment_threshold = 0.0 # Explicitly set for clarity
        decision = self.model.decide(df, {})

        # 4. Assert
        self.assertEqual(decision.action, "hold")

    def test_decision_hold_on_no_crossover(self):
        """Test that a 'hold' decision is made if there is no crossover."""
        # 1. Prepare data: Positive sentiment news
        articles = [
            NewsArticle(
                source="test", headline="Good News", url="http://test.com/1",
                published_at=datetime.now(timezone.utc) - timedelta(hours=1),
                sentiment_score=0.8, sentiment_label="positive"
            )
        ]
        upsert_news_articles(self.conn, articles)

        # 2. Create dataframe without a crossover event
        df = self._create_dummy_dataframe(crossover=False)

        # 3. Get decision
        decision = self.model.decide(df, {})

        # 4. Assert
        self.assertEqual(decision.action, "hold")


class TestPlaceholderMLModel(unittest.TestCase):
    """Unit tests for the PlaceholderMLModel."""

    def test_load_model(self):
        """Test that the model simulation works."""
        model = PlaceholderMLModel(model_path="/fake/path/model.pkl")
        self.assertIsNotNone(model.model)
        self.assertEqual(model.model['name'], 'PlaceholderPredictor')

    def test_decide_returns_hold(self):
        """Test that the placeholder always returns a 'hold' decision."""
        model = PlaceholderMLModel(model_path="/fake/path/model.pkl")
        df = pd.DataFrame({'close': [100, 101]})
        decision = model.decide(df, {})
        self.assertEqual(decision.action, "hold")

if __name__ == '__main__':
    unittest.main()
