"""
A Freqtrade strategy designed specifically for integration testing.

This strategy uses the RuleBasedModel to make decisions and is configured
to read from a database path specified in the configuration file, allowing
tests to inject a temporary, isolated database.
"""

import sqlite3
from pathlib import Path
import pandas as pd
import talib as ta
import qtpylib
from freqtrade.strategy import IStrategy

# Assuming the execution context allows this import path
from app.reasoning.rule_based_model import RuleBasedModel
from app.strategies.persistence.sqlite import ensure_schema


class IntegrationTestStrategy(IStrategy):
    """A strategy that integrates a reasoning model for integration tests."""

    minimal_roi = {"0": 0.01}
    stoploss = -0.10
    timeframe = '5m'

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

        # Generate a crossover signal for the test
        # This mimics the logic inside the RuleBasedModel for testing purposes
        dataframe['fast_ma'] = ta.SMA(dataframe['close'], timeperiod=10)
        dataframe['slow_ma'] = ta.SMA(dataframe['close'], timeperiod=25)

        crossover_signal = (qtpylib.crossed_above(dataframe['fast_ma'], dataframe['slow_ma']))

        dataframe['enter_long'] = 0
        if decision.action == 'buy':
            dataframe.loc[crossover_signal, 'enter_long'] = 1
            
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # For testing, we can use a simple exit condition, e.g., exit if price decreases.
        # This is just to ensure Freqtrade can execute a trade.
        # In a real scenario, this would be a proper exit signal.
        dataframe['exit_long'] = 0
        # Example: exit on the candle after entry for simplicity
        if 'enter_long' in dataframe.columns:
            dataframe.loc[
                (dataframe['enter_long'].shift(1) == 1), 'exit_long'
            ] = 1
        return dataframe
