from __future__ import annotations

from datetime import datetime
from typing import Dict

import pandas as pd
from freqtrade.strategy import IntParameter
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame


class MaCrossoverStrategy(IStrategy):
    """En enkel EMA-crossover-strategi som lämpar sig för nybörjare och demo.

    Signaler:
    - Köp när kort EMA korsar över lång EMA.
    - Sälj när kort EMA korsar under lång EMA.

    Justera parametrar via hyperopt eller direkt i koden.
    """

    # Grundinställningar
    timeframe: str = "5m"
    startup_candle_count: int = 200
    process_only_new_candles: bool = True

    # Risk (enkel baseline, finjustera efter backtests)
    minimal_roi: Dict[str, float] = {"0": 0.03}
    stoploss: float = -0.10

    # Hyperoptbara parametrar
    ema_short = IntParameter(5, 50, default=12, space="buy")
    ema_long = IntParameter(20, 200, default=26, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        # Säkerställ sorterad data
        df = dataframe.sort_index()

        # EMA-beräkningar (utan externa beroenden)
        df["ema_short"] = df["close"].ewm(span=int(self.ema_short.value), adjust=False).mean()
        df["ema_long"] = df["close"].ewm(span=int(self.ema_long.value), adjust=False).mean()

        # Volymfilter (enkel)
        df["volume_mean"] = df["volume"].rolling(window=20, min_periods=20).mean()

        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        df = dataframe.copy()
        df["enter_long"] = (
            (df["ema_short"] > df["ema_long"]) &
            (df["volume"] > 0) &
            (df["volume_mean"].fillna(0) > 0)
        )

        df.loc[df["enter_long"], ["enter_long", "enter_tag"]] = (1, "ema_crossover")
        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        df = dataframe.copy()
        df["exit_long"] = (
            (df["ema_short"] < df["ema_long"]) &
            (df["volume"] > 0)
        )

        df.loc[df["exit_long"], ["exit_long", "exit_tag"]] = (1, "ema_crossdown")
        return df
