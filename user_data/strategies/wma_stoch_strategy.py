from __future__ import annotations
import logging
from functools import reduce
from typing import Dict, List

log = logging.getLogger(__name__)

from decimal import Decimal
import numpy as np
import pandas as pd
from freqtrade.strategy import IntParameter, DecimalParameter
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame


class WmaStochSwingStrategy(IStrategy):
    """Trend + oscillator swing: WMA-trendfilter + Stochastic %K/%D korsningar.

    Hypotes:
    - Långa trades i övergripande upptrend (pris över lång WMA), inträde på
      %K cross-upp över %D från översålt zon.
    - Exit när oscillatorn signalerar överköpt/avtagande momentum eller trend bryts.
    """

    timeframe: str = "5m"
    startup_candle_count: int = 300
    process_only_new_candles: bool = True

    minimal_roi: Dict[str, float] = {"0": 0.03}
    stoploss: float = -0.12

    trailing_stop: bool = True
    trailing_stop_positive: float = 0.01
    trailing_stop_positive_offset: float = 0.03
    trailing_only_offset_is_reached: bool = True

    # Hyperoptbara parametrar
    wma_fast = IntParameter(20, 100, default=50, space="buy")
    wma_slow = IntParameter(100, 400, default=200, space="buy")
    stoch_k = IntParameter(7, 21, default=14, space="buy")
    stoch_d = IntParameter(3, 9, default=3, space="buy")
    k_buy_max = IntParameter(10, 40, default=30, space="buy")
    k_sell_min = IntParameter(60, 90, default=70, space="buy")

    # Volatilitetsstyrd position sizing (hyperoptbar)
    risk_per_trade = DecimalParameter(0.002, 0.02, decimals=3, default=0.010, space="buy")
    atr_stop_mult = DecimalParameter(1.5, 4.0, decimals=1, default=2.0, space="buy")
    max_stake_pct = DecimalParameter(0.02, 0.20, decimals=2, default=0.10, space="buy")

    plot_config = {
        "main_plot": {
            "wma_fast": {},
            "wma_slow": {},
        },
        "subplots": {
            "Stoch": {"stoch_k": {}, "stoch_d": {}},
            "ATR": {"atr": {}},
        },
    }

    @staticmethod
    def _wma(series: pd.Series, period: int) -> pd.Series:
        if period <= 1:
            return series
        weights = np.arange(1, period + 1)
        return series.rolling(period).apply(lambda x: float(np.dot(x, weights)) / weights.sum(), raw=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        log.debug(f"Populating indicators for {metadata['pair']}... Shape: {dataframe.shape}")
        df = dataframe.sort_index()

        f = int(self.wma_fast.value)
        s = int(self.wma_slow.value)
        df["wma_fast"] = self._wma(df["close"], f)
        df["wma_slow"] = self._wma(df["close"], s)

        # Stochastic
        k_len = int(self.stoch_k.value)
        d_len = int(self.stoch_d.value)
        lowest_low = df["low"].rolling(k_len, min_periods=k_len).min()
        highest_high = df["high"].rolling(k_len, min_periods=k_len).max()
        denom = (highest_high - lowest_low).replace(0, np.nan)
        stoch_k = 100 * (df["close"] - lowest_low) / denom
        df["stoch_k"] = stoch_k.rolling(1).mean()  # smoothing hook if needed
        df["stoch_d"] = df["stoch_k"].rolling(d_len, min_periods=d_len).mean()

        # ATR
        atr_n = 14
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_n, min_periods=atr_n).mean()

        # Volymmedel
        df["volume_mean"] = df["volume"].rolling(window=20, min_periods=20).mean()

        log.debug(f"Indicators populated for {metadata['pair']}. WMA/Stoch values added.")
        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        log.debug(f"Populating entry trend for {metadata['pair']}...")
        df = dataframe.copy()
        # Uptrend + K cross up D from oversold
        cross_up = (df["stoch_k"] > df["stoch_d"]) & (df["stoch_k"].shift(1) <= df["stoch_d"].shift(1))
        df["enter_long"] = (
            (df["close"] > df["wma_slow"]) &
            (df["wma_fast"] > df["wma_slow"]) &
            cross_up &
            (df["stoch_k"] < int(self.k_buy_max.value)) &
            (df["volume"] > 0) &
            (df["volume_mean"].fillna(0) > 0)
        )
        df.loc[df["enter_long"], "enter_tag"] = "wma_stoch_long"

        entry_signals = df[df["enter_long"] == True]
        if not entry_signals.empty:
            log.info(f"{metadata['pair']}: {len(entry_signals)} entry signals found.")

        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        log.debug(f"Populating exit trend for {metadata['pair']}...")
        df = dataframe.copy()
        cross_down = (df["stoch_k"] < df["stoch_d"]) & (df["stoch_k"].shift(1) >= df["stoch_d"].shift(1))
        df["exit_long"] = (
            (cross_down & (df["stoch_k"] > int(self.k_sell_min.value))) |
            (df["close"] < df["wma_fast"]) &
            (df["volume"] > 0)
        )
        df.loc[df["exit_long"], "exit_tag"] = "stoch_revert_or_trend_break"

        exit_signals = df[df["exit_long"] == True]
        if not exit_signals.empty:
            log.info(f"{metadata['pair']}: {len(exit_signals)} exit signals found.")

        return df

    # --- Risk/position sizing ---
    def custom_stake_amount(
        self,
        pair: str,
        current_time,  # datetime
        current_rate: float,
        **kwargs,
    ) -> Optional[float]:
        if not hasattr(self, "dp") or self.dp is None:
            return None
        try:
            df, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        except Exception:
            return None
        if df is None or df.empty:
            return None
        last = df.iloc[-1]
        atr = float(last.get("atr", float("nan")))
        close = float(last.get("close", current_rate))
        if not (atr and close) or atr <= 0 or close <= 0:
            return None
        stop_fraction = (atr * float(self.atr_stop_mult.value)) / close
        if not (0.001 <= stop_fraction <= 0.2):
            return None
        free_stake = None
        try:
            if hasattr(self, "wallets") and self.wallets:
                free_stake = float(self.wallets.get_free(self.stake_currency))
        except Exception:
            free_stake = None
        if free_stake is None or free_stake <= 0:
            return None
        risk_amount = free_stake * float(self.risk_per_trade.value)
        if risk_amount <= 0:
            return None
        raw_stake = risk_amount / max(stop_fraction, 1e-9)
        max_stake = free_stake * float(self.max_stake_pct.value)
        stake = max(0.0, min(raw_stake, max_stake))
        if stake < 10:
            return None
        return float(Decimal(stake).quantize(Decimal("0.01")))
