from __future__ import annotations

from typing import Dict
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame


class HodlStrategy(IStrategy):
    """Enkel HODL-baseline.

    Idé: Köp en gång och håll. Inga exits via signaler, ingen trailing.
    Används som referens mot aktiva strategier i backtester.
    """

    timeframe: str = "5m"
    startup_candle_count: int = 1
    process_only_new_candles: bool = True

    # Effektivt ingen ROI-exit
    minimal_roi: Dict[str, float] = {"0": 1000.0}
    stoploss: float = -0.99

    trailing_stop: bool = False

    # Styr exits via flaggor: inga exits från signaler
    use_exit_signal: bool = False
    exit_profit_only: bool = False

    plot_config = {"main_plot": {}, "subplots": {}}

    def populate_indicators(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        df = dataframe.copy()
        # En enda entry vid första raden (shift(1) är NaN på första baren)
        df["enter_long"] = df["close"].notna() & df["close"].shift(1).isna() & (df["volume"] > 0)
        df.loc[df["enter_long"], "enter_tag"] = "hodl"
        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        # Inga exit-signaler används
        return dataframe
