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
        num_periods = 30
        dates = pd.to_datetime(pd.date_range(
            start="2023-01-01", periods=num_periods, freq="5min", tz="UTC"
        ))

        if crossover:
            prices = [100] * 28 + [110, 111]
        else:
            prices = [110] * 28 + [100, 99]

        df = pd.DataFrame({'date': dates, 'close': prices})
        return df

    def _prepare_sentiment_data(self, df: pd.DataFrame, score: float, label: str):
        """Helper to create and insert a news article with a relevant timestamp."""
        last_candle_time = df.iloc[-1]['date'].to_pydatetime()
        article_time = last_candle_time - timedelta(minutes=30)
        article = NewsArticle(
            source="test", headline=f"{label} News", url="http://test.com/1",
            published_at=article_time,
            symbols=['BTC/USDT'],
            sentiment_score=score, sentiment_label=label
        )
        upsert_news_articles(self.conn, [article])

    def test_decision_buy_on_crossover_and_positive_sentiment(self):
        """Test that a 'buy' decision is made with positive signals."""
        df = self._create_dummy_dataframe(crossover=True)
        self._prepare_sentiment_data(df, 0.8, "positive")

        decision = self.model.decide(df, {})

        self.assertEqual(decision.action, "buy")
        self.assertIn("confirmed by positive sentiment", decision.reason)

    def test_decision_hold_on_crossover_but_negative_sentiment(self):
        """Test that a 'hold' decision is made if sentiment is negative."""
        df = self._create_dummy_dataframe(crossover=True)
        self._prepare_sentiment_data(df, -0.8, "negative")

        self.model.sentiment_threshold = 0.0
        decision = self.model.decide(df, {})

        self.assertEqual(decision.action, "hold")

    def test_decision_hold_on_no_crossover(self):
        """Test that a 'hold' decision is made if there is no crossover."""
        df = self._create_dummy_dataframe(crossover=False)
        self._prepare_sentiment_data(df, 0.8, "positive")

        decision = self.model.decide(df, {})

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
