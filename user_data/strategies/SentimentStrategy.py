# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement

import logging
import sqlite3
from pathlib import Path

import freqtrade.vendor.qtpylib.indicators as qtpylib
import pandas as pd
from freqtrade.strategy import IntParameter, IStrategy, StringParameter

from app.reasoning.ml_model import PlaceholderMLModel
from app.reasoning.models import BaseReasoningModel
from app.reasoning.rule_based_model import RuleBasedModel
from app.strategies.persistence.sqlite import connect

logger = logging.getLogger(__name__)


class SentimentStrategy(IStrategy):
    """
    A strategy that delegates its decision-making to a configurable 'Reasoning Model'.

    This decouples the Freqtrade strategy boilerplate from the core trading logic,
    allowing different models (rule-based, ML, etc.) to be plugged in.
    """

    # --- Strategy parameters ---
    minimal_roi = {"0": 0.15, "30": 0.1, "60": 0.05}
    stoploss = -0.10
    trailing_stop = False
    timeframe = "5m"

    # --- Model Selection ---
    # Select which reasoning model to use: 'rule_based' or 'ml_placeholder'
    reasoning_model_name = StringParameter(
        ["rule_based", "ml_placeholder"], default="rule_based", space="buy"
    )

    # --- Hyperoptable parameters for the RuleBasedModel ---
    fast_ma = IntParameter(5, 20, default=10, space="buy")
    slow_ma = IntParameter(20, 50, default=25, space="buy")
    sentiment_lookback_hours = IntParameter(12, 72, default=24, space="buy")

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.db_path = Path(config["user_data_dir"]) / "backtest_results" / "index.db"
        self._db_conn: sqlite3.Connection | None = None
        self.model: BaseReasoningModel | None = None

    @property
    def db_conn(self) -> sqlite3.Connection:
        """Lazy-loads a database connection."""
        if self._db_conn is None:
            self._db_conn = connect(self.db_path)
        return self._db_conn

    def _get_model(self) -> BaseReasoningModel:
        """Initializes and returns the selected reasoning model."""
        if self.reasoning_model_name.value == "rule_based":
            return RuleBasedModel(
                db_conn=self.db_conn,
                fast_ma=self.fast_ma.value,
                slow_ma=self.slow_ma.value,
                sentiment_lookback_hours=self.sentiment_lookback_hours.value,
            )
        if self.reasoning_model_name.value == "ml_placeholder":
            # In a real scenario, the path might come from config
            model_path = self.config["user_data_dir"] / "models" / "predictor.pkl"
            return PlaceholderMLModel(model_path=model_path)

        raise ValueError(f"Unknown reasoning model: {self.reasoning_model_name.value}")

    def bot_loop_start(self, **kwargs) -> None:
        """Initialize the model at the start of the loop."""
        super().bot_loop_start(**kwargs)
        self.model = self._get_model()

    def bot_loop_end(self, **kwargs) -> None:
        """Clean up resources at the end of the loop."""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None
        return super().bot_loop_end(**kwargs)

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Indicators required by the RuleBasedModel are populated here.
        # A more advanced implementation might have the model declare its indicator needs.
        dataframe["fast_ma"] = qtpylib.sma(dataframe["close"], self.fast_ma.value)
        dataframe["slow_ma"] = qtpylib.sma(dataframe["close"], self.slow_ma.value)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        if not self.model:
            dataframe["enter_long"] = 0
            return dataframe

        # For performance, we ask the model for a single decision based on the full history.
        decision = self.model.decide(dataframe, metadata)

        # The model's decision is applied to the last candle.
        # Freqtrade will use this to enter a trade on the next candle.
        dataframe.loc[dataframe.index[-1], "enter_long"] = 1 if decision.action == "buy" else 0

        if decision.action == "buy":
            logger.info(f"Decision: BUY. Reason: {decision.reason}. Metadata: {decision.metadata}")

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Exit logic remains simple for now, handled by ROI/stoploss.
        # A more complex model could also provide sell decisions.
        dataframe["exit_long"] = 0
        return dataframe
