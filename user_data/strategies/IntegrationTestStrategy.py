"""
A Freqtrade strategy designed specifically for integration testing.

This strategy uses the RuleBasedModel to make decisions and is configured
to read from a database path specified in the configuration file, allowing
tests to inject a temporary, isolated database.
"""

import sqlite3
from pathlib import Path

import pandas as pd
from freqtrade.strategy import IStrategy

# Assuming the execution context allows this import path
from app.reasoning.rule_based_model import RuleBasedModel
from app.strategies.persistence.sqlite import ensure_schema


class IntegrationTestStrategy(IStrategy):
    """A strategy that integrates a reasoning model for integration tests."""

    minimal_roi = {"0": 0.01}
    stoploss = -0.10
    timeframe = '5m'
    can_short = False
    # Ensure freqtrade consumes our exit signals
    use_exit_signal = True      # new-style exit_long
    use_sell_signal = True      # legacy sell
    # Allow exit regardless of profitability to guarantee closure in tests
    sell_profit_only = False
    exit_profit_only = False
    # Ensure enough candles for indicators/crossover logic
    startup_candle_count = 25

    def __init__(self, config: dict, *args, **kwargs):
        super().__init__(config, *args, **kwargs)

        # Get the database path from the custom config section.
        # This makes the strategy testable with a temporary DB.
        db_path_str = config.get('custom_config', {}).get('db_path', ':memory:')
        self.db_path = Path(db_path_str)

        # Each strategy instance gets its own connection and model.
        self.db_conn = sqlite3.connect(self.db_path)
        ensure_schema(self.db_conn, with_extended=True)
        self.model = RuleBasedModel(self.db_conn)

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """The model handles its own indicators."""
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Use the reasoning model to decide on an entry signal."""
        # The decision model is called, but for this integration test, we need to
        # ensure the signal is correctly placed on the dataframe for the backtest engine.
        # The RuleBasedModel's logic is what we're ultimately testing, but the signal
        # must be set in a way the backtester can process.

        decision = self.model.decide(dataframe, metadata)

        # Generate a crossover signal for the test using pandas (no TA-Lib)
        dataframe['fast_ma'] = (
            dataframe['close'].rolling(window=10, min_periods=10).mean()
        )
        dataframe['slow_ma'] = (
            dataframe['close'].rolling(window=25, min_periods=25).mean()
        )

        # Bullish crossover when fast crosses above slow on this candle
        crossover_signal = (
            (dataframe['fast_ma'] > dataframe['slow_ma'])
            & (dataframe['fast_ma'].shift(1) <= dataframe['slow_ma'].shift(1))
        )

        dataframe['enter_long'] = 0
        if decision.action == 'buy':
            if crossover_signal.any():
                dataframe.loc[crossover_signal, 'enter_long'] = 1
            else:
                # Fallback to ensure one trade in the positive sentiment case:
                # mark the penultimate candle to guarantee execution, and the exit
                # logic will close on the last candle.
                if len(dataframe) >= 2:
                    dataframe.loc[dataframe.index[-2], 'enter_long'] = 1

        # If entry would occur too late (last or penultimate), shift it to third-to-last
        if len(dataframe) >= 3:
            if dataframe.iloc[-1]['enter_long'] == 1 or dataframe.iloc[-2]['enter_long'] == 1:
                dataframe.loc[dataframe.index[-1], 'enter_long'] = 0
                dataframe.loc[dataframe.index[-2], 'enter_long'] = 0
                dataframe.loc[dataframe.index[-3], 'enter_long'] = 1

        # Legacy compatibility for some freqtrade versions
        dataframe['buy'] = dataframe['enter_long']
        # Optional: tag entries for easier inspection
        dataframe['enter_tag'] = ''
        if (dataframe['enter_long'] == 1).any():
            dataframe.loc[dataframe['enter_long'] == 1, 'enter_tag'] = 'itest'

        # Debug summary (stdout captured by runner)
        try:
            total_entries = int(dataframe['enter_long'].sum())
            print(f"[IntegrationTestStrategy] entry_signals={total_entries}")
        except Exception:
            pass

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Simple exit condition for testing only: exit on the candle after entry
        dataframe['exit_long'] = 0
        # Example: exit on the candle after entry for simplicity
        if 'enter_long' in dataframe.columns:
            dataframe.loc[
                (dataframe['enter_long'].shift(1) == 1), 'exit_long'
            ] = 1
        # Legacy compatibility
        dataframe['sell'] = dataframe['exit_long']
        try:
            total_exits = int(dataframe['exit_long'].sum())
            print(f"[IntegrationTestStrategy] exit_signals={total_exits}")
        except Exception:
            pass
        return dataframe
