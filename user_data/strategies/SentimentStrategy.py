# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import pandas as pd
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, IntParameter

from app.strategies.persistence.sqlite import connect, get_news_articles_in_range

logger = logging.getLogger(__name__)


class SentimentStrategy(IStrategy):
    """
    A trading strategy that combines a simple moving average (MA) crossover signal
    with a sentiment score derived from recent news articles.

    Entry signal is only generated if:
    1. The fast MA crosses above the slow MA.
    2. The average sentiment score of news from the last `sentiment_lookback_hours` is positive.
    """

    # --- Strategy parameters ---
    minimal_roi = {"0": 0.15, "30": 0.1, "60": 0.05}
    stoploss = -0.10
    trailing_stop = False
    timeframe = "5m"

    # --- Indicator parameters ---
    fast_ma = IntParameter(5, 20, default=10, space="buy")
    slow_ma = IntParameter(20, 50, default=25, space="buy")

    # --- Sentiment parameters ---
    sentiment_lookback_hours = IntParameter(12, 72, default=24, space="buy")
    sentiment_threshold = 0.0  # Neutral or positive sentiment required

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.db_path = Path(config["user_data_dir"]) / "backtest_results" / "index.db"
        self._db_conn = None

    @property
    def db_conn(self) -> sqlite3.Connection:
        """Lazy-loads a database connection."""
        if self._db_conn is None:
            self._db_conn = connect(self.db_path)
        return self._db_conn

    def get_average_sentiment(self, current_time_utc: datetime) -> float:
        """Fetches news and calculates average sentiment over a lookback period."""
        lookback_start_utc = current_time_utc - timedelta(
            hours=self.sentiment_lookback_hours.value
        )

        try:
            articles = get_news_articles_in_range(
                self.db_conn, lookback_start_utc, current_time_utc
            )
            if not articles:
                return 0.0  # Neutral sentiment if no news

            scores = [a["sentiment_score"] for a in articles if a["sentiment_score"] is not None]
            return sum(scores) / len(scores) if scores else 0.0

        except Exception as e:
            logger.error(f"Error fetching or processing sentiment: {e}")
            return 0.0 # Fail-safe to neutral

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe[f"fast_ma"] = qtpylib.sma(dataframe["close"], self.fast_ma.value)
        dataframe[f"slow_ma"] = qtpylib.sma(dataframe["close"], self.slow_ma.value)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Calculate sentiment for each candle
        sentiments = []
        for i in range(len(dataframe)):
            current_time = dataframe['date'].iloc[i].to_pydatetime().replace(tzinfo=timezone.utc)
            avg_sentiment = self.get_average_sentiment(current_time)
            sentiments.append(avg_sentiment)
        
        dataframe['sentiment_score'] = sentiments

        # MA Crossover condition
        ma_crossover = qtpylib.crossed_above(
            dataframe[f"fast_ma"],
            dataframe[f"slow_ma"],
        )

        # Sentiment condition
        sentiment_ok = dataframe["sentiment_score"] > self.sentiment_threshold

        # Combined entry condition
        dataframe.loc[
            (
                ma_crossover & sentiment_ok
            ),
            "enter_long",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Simple exit: cross below
        dataframe.loc[
            (qtpylib.crossed_below(dataframe[f"fast_ma"], dataframe[f"slow_ma"])),
            "exit_long",
        ] = 1
        return dataframe

    def bot_loop_start(self, **kwargs) -> None:
        """Close DB connection at the end of a backtest run."""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None
        return super().bot_loop_start(**kwargs)

