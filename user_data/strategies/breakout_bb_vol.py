from __future__ import annotations

from typing import Dict, Optional
from decimal import Decimal

import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IntParameter, DecimalParameter
from freqtrade.strategy.interface import IStrategy


class BreakoutBbVolStrategy(IStrategy):
    """Breakout-strategi med BB-width och volymspik.

    Hypotes:
    - Köp när pris bryter över ett nyligt motstånd (Donchian high) tillsammans med
      expanderande volatilitet (BB-width) och volymspik.
    - Sälj vid momentum-avmattning eller trailing stop.
    """

    timeframe: str = "5m"
    startup_candle_count: int = 200
    process_only_new_candles: bool = True

    minimal_roi: Dict[str, float] = {
        "0": 0.06,
        "60": 0.03,
        "180": 0.0,
    }
    stoploss: float = -0.10

    trailing_stop: bool = True
    trailing_stop_positive: float = 0.01
    trailing_stop_positive_offset: float = 0.03
    trailing_only_offset_is_reached: bool = True

    # Hyperoptbara parametrar
    bb_window = IntParameter(14, 40, default=20, space="buy")
    bb_width_min = DecimalParameter(0.015, 0.08, decimals=3, default=0.030, space="buy")
    donchian_window = IntParameter(20, 60, default=40, space="buy")
    vol_window = IntParameter(20, 60, default=30, space="buy")
    vol_spike_mult = DecimalParameter(1.2, 3.0, decimals=1, default=1.8, space="buy")

    # Sizing
    risk_per_trade = DecimalParameter(0.002, 0.02, decimals=3, default=0.010, space="buy")
    atr_stop_mult = DecimalParameter(1.5, 4.0, decimals=1, default=2.5, space="buy")
    max_stake_pct = DecimalParameter(0.02, 0.20, decimals=2, default=0.07, space="buy")

    plot_config = {
        "main_plot": {
            "dc_high": {},
            "bb_upper": {},
            "bb_lower": {},
        },
        "subplots": {
            "BBWidth": {"bb_width": {}},
            "Vol": {"volume": {}, "volume_mean": {}},
            "ATR": {"atr": {}},
        },
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        df = dataframe.sort_index()

        # Bollinger Bands + width
        win = int(self.bb_window.value)
        sma = df["close"].rolling(win, min_periods=win).mean()
        std = df["close"].rolling(win, min_periods=win).std(ddof=0)
        df["bb_upper"] = sma + 2.0 * std
        df["bb_lower"] = sma - 2.0 * std
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma

        # Donchian channel high (resistans)
        dcw = int(self.donchian_window.value)
        df["dc_high"] = df["high"].rolling(dcw, min_periods=dcw).max()

        # Volym medel och spike
        vw = int(self.vol_window.value)
        df["volume_mean"] = df["volume"].rolling(vw, min_periods=vw).mean()
        df["vol_spike"] = df["volume"] > (float(self.vol_spike_mult.value) * df["volume_mean"])  # boolean

        # ATR (14)
        atr_n = 14
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_n, min_periods=atr_n).mean()

        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        df = dataframe.copy()
        df["enter_long"] = (
            (df["close"] > df["dc_high"].shift(1)) &  # bryt förbi tidigare max
            (df["bb_width"] > float(self.bb_width_min.value)) &
            (df["vol_spike"]) &
            (df["volume"] > 0)
        )
        df.loc[df["enter_long"], "enter_tag"] = "breakout_bb_vol"
        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        df = dataframe.copy()
        # Enkel exit: close under BB-upper efter breakout (svaghet) – trailing hanterar vinster
        df["exit_long"] = (
            (df["close"] < df["bb_upper"].shift(1)) &
            (df["volume"] > 0)
        )
        df.loc[df["exit_long"], "exit_tag"] = "breakout_weakness"
        return df

    def custom_stake_amount(
        self,
        pair: str,
        current_time,
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

        risk_frac = float(self.risk_per_trade.value)
        risk_amount = free_stake * risk_frac
        if risk_amount <= 0:
            return None

        raw_stake = risk_amount / max(stop_fraction, 1e-9)
        max_stake = free_stake * float(self.max_stake_pct.value)
        stake = max(0.0, min(raw_stake, max_stake))
        if stake < 10:
            return None
        return float(Decimal(stake).quantize(Decimal("0.01")))
