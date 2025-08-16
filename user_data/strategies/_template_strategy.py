from __future__ import annotations

from typing import Dict, Optional
from decimal import Decimal

import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IntParameter, DecimalParameter
from freqtrade.strategy.interface import IStrategy


class TemplateStrategy(IStrategy):
    """Template for Freqtrade strategies (2025.7 compatible).

    Usage:
    - Copy this file and rename class and filename.
    - Fill indicators in populate_indicators() only (no side-effects).
    - Implement entry/exit rules with clear, boolean columns.
    - Use hyperopt parameters via IntParameter/DecimalParameter.
    - Keep custom_stake_amount signature with **kwargs (2025.7).
    """

    timeframe: str = "5m"
    startup_candle_count: int = 200
    process_only_new_candles: bool = True

    minimal_roi: Dict[str, float] = {
        "0": 0.05,
        "60": 0.02,
        "180": 0.0,
    }
    stoploss: float = -0.1

    trailing_stop: bool = True
    trailing_stop_positive: float = 0.01
    trailing_stop_positive_offset: float = 0.03
    trailing_only_offset_is_reached: bool = True

    # Hyperopt parameters (example)
    rsi_len = IntParameter(7, 21, default=14, space="buy")
    rsi_buy = IntParameter(50, 70, default=60, space="buy")
    rsi_exit = IntParameter(30, 55, default=45, space="sell")

    # Sizing (example ATR-based)
    risk_per_trade = DecimalParameter(0.002, 0.02, decimals=3, default=0.01, space="buy")
    atr_stop_mult = DecimalParameter(1.5, 4.0, decimals=1, default=2.0, space="buy")
    max_stake_pct = DecimalParameter(0.02, 0.20, decimals=2, default=0.07, space="buy")

    plot_config = {
        "main_plot": {},
        "subplots": {
            "RSI": {"rsi": {}},
            "ATR": {"atr": {}},
        },
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        df = dataframe.sort_index()

        # Example RSI
        rsi_len = int(self.rsi_len.value)
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=rsi_len, min_periods=rsi_len).mean()
        avg_loss = loss.rolling(window=rsi_len, min_periods=rsi_len).mean()
        rs = avg_gain / (avg_loss.replace(0, 1e-10))
        df["rsi"] = 100 - (100 / (1 + rs))

        # Example ATR(14)
        atr_n = 14
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_n, min_periods=atr_n).mean()

        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        df = dataframe.copy()
        df["enter_long"] = (df["rsi"] > int(self.rsi_buy.value)) & (df["volume"] > 0)
        df.loc[df["enter_long"], "enter_tag"] = "template_entry"
        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        df = dataframe.copy()
        df["exit_long"] = (df["rsi"] < int(self.rsi_exit.value)) & (df["volume"] > 0)
        df.loc[df["exit_long"], "exit_tag"] = "template_exit"
        return df

    def custom_stake_amount(
        self,
        pair: str,
        current_time,
        current_rate: float,
        **kwargs,
    ) -> Optional[float]:
        # ATR-based example
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
