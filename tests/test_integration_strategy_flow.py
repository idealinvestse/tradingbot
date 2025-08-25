"""
Integration tests for the full strategy flow, using the runner module.
"""

import unittest
import tempfile
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd

from app.data_services.models import NewsArticle
from app.strategies.persistence.sqlite import ensure_schema, upsert_news_articles
from app.strategies.runner import run_backtest


class TestFullStrategyFlow(unittest.TestCase):
    """Test the full backtest flow using the runner."""

    def setUp(self):
        """Create a temporary directory for all test artifacts."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.user_data_path = self.temp_path / 'user_data'
        self.user_data_path.mkdir()
        strategies_path = self.user_data_path / 'strategies'
        strategies_path.mkdir()
        (self.user_data_path / 'data' / 'binance').mkdir(parents=True, exist_ok=True)

        # Copy the strategy file to the temporary directory
        source_strategy_path = Path(__file__).parent.parent / 'user_data' / 'strategies' / 'IntegrationTestStrategy.py'
        dest_strategy_path = strategies_path / 'IntegrationTestStrategy.py'
        dest_strategy_path.write_text(source_strategy_path.read_text())

    def tearDown(self):
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    def _prepare_config(self, db_path: Path) -> Path:
        """Create a temporary Freqtrade config file."""
        config_path = self.user_data_path / 'config.json'
        config = {
            "exchange": {
                "name": "binance",
                "key": "",
                "secret": "",
                "pair_whitelist": ["BTC/USDT"]
            },
            "pairlists": [
                {"method": "StaticPairList"}
            ],
            "stake_currency": "USDT",
            "stake_amount": "unlimited",
            "max_open_trades": 10,
            "entry_pricing": {
                "price_side": "ask",
                "use_order_book": False
            },
            "exit_pricing": {
                "price_side": "bid",
                "use_order_book": False
            },
            "datadir": str(self.user_data_path / 'data' / 'binance'),
            "exportdir": str(self.user_data_path / 'backtest_results'),
            "custom_config": {
                "db_path": str(db_path)
            }
        }
        with open(config_path, 'w') as f:
            json.dump(config, f)
        return config_path

    def _prepare_ohlcv_data(self, crossover: bool):
        """Create a dummy OHLCV data file for Freqtrade."""
        data_dir = self.user_data_path / 'data' / 'binance'
        data_file = data_dir / 'BTC_USDT-5m.feather'

        num_periods = 40 # Need enough data for indicators
        dates = pd.to_datetime(pd.date_range(
            start="2023-01-01", periods=num_periods, freq="5min", tz="UTC"
        ))

        if crossover:
            prices = [100] * 38 + [110, 111]
        else:
            prices = [110] * 38 + [100, 99]
        
        df = pd.DataFrame({
            'open': prices,
            'high': [p * 1.02 for p in prices],
            'low': [p * 0.98 for p in prices],
            'close': prices,
            'volume': [1000] * num_periods
        }, index=dates)
        df.index.name = 'date'
        df.reset_index(inplace=True)

        # Save as Feather, which is the default format for Freqtrade
        df.to_feather(data_file)

    def _prepare_sentiment_data(self, db_path: Path, score: float, label: str):
        """Create and insert a news article into the temporary database."""
        conn = sqlite3.connect(db_path)
        ensure_schema(conn, with_extended=True)
        article_time = datetime(2023, 1, 1, 3, 10, tzinfo=timezone.utc)
        article = NewsArticle(
            source="test", headline=f"{label} News", url="http://test.com/1",
            published_at=article_time,
            symbols=['BTC/USDT'],
            sentiment_score=score, sentiment_label=label
        )
        upsert_news_articles(conn, [article])
        conn.close()

    def test_flow_generates_buy_signal(self):
        """Verify the full flow generates a trade with positive signals."""
        db_path = self.temp_path / 'test.db'
        config_path = self._prepare_config(db_path)
        self._prepare_ohlcv_data(crossover=True)
        self._prepare_sentiment_data(db_path, 0.8, "positive")

        result = run_backtest(
            config_path=config_path,
            strategy='IntegrationTestStrategy',
            timerange='20230101-20230102',
            timeframe='5m',
            cwd=self.temp_path # Run from temp dir to ensure isolation
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        
        # Check that a trade was actually executed
        results_file = self.user_data_path / 'backtest_results' / 'trades.json'
        self.assertTrue(results_file.exists())
        with open(results_file, 'r') as f:
            trades = json.load(f)
        self.assertEqual(len(trades['trades']), 1)
        self.assertEqual(trades['trades'][0]['pair'], 'BTC/USDT')

    def test_flow_generates_no_signal(self):
        """Verify the full flow generates no trade with negative sentiment."""
        db_path = self.temp_path / 'test.db'
        config_path = self._prepare_config(db_path)
        self._prepare_ohlcv_data(crossover=True)
        self._prepare_sentiment_data(db_path, -0.8, "negative")

        result = run_backtest(
            config_path=config_path,
            strategy='IntegrationTestStrategy',
            timerange='20230101-20230102',
            timeframe='5m',
            cwd=self.temp_path
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

        results_file = self.user_data_path / 'backtest_results' / 'trades.json'
        self.assertTrue(results_file.exists())
        with open(results_file, 'r') as f:
            trades = json.load(f)
        self.assertEqual(len(trades['trades']), 0)

