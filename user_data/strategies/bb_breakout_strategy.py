from __future__ import annotations

from typing import Dict, Optional

from decimal import Decimal
import pandas as pd
from freqtrade.strategy import IntParameter, DecimalParameter
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame


class BollingerBreakoutStrategy(IStrategy):
    """Bollinger Band Breakout med volymspik och squeeze-filter.

    Hypotes:
    - Brytning över övre band efter en squeeze fas (låg BB-width) med samtidiga
      volymspikar signalerar momentum-start och edge för long.
    """

    timeframe: str = "5m"
    startup_candle_count: int = 200
    process_only_new_candles: bool = True

    minimal_roi: Dict[str, float] = {"0": 0.03}
    stoploss: float = -0.12

    trailing_stop: bool = True
    trailing_stop_positive: float = 0.01
    trailing_stop_positive_offset: float = 0.03
    trailing_only_offset_is_reached: bool = True

    # Hyperoptbara parametrar (köpfilter)
    bb_window = IntParameter(14, 40, default=20, space="buy")
    bb_min_width = DecimalParameter(0.008, 0.060, decimals=3, default=0.015, space="buy")
    squeeze_lb = IntParameter(30, 100, default=50, space="buy")
    width_expansion_mult = DecimalParameter(1.1, 1.8, decimals=2, default=1.3, space="buy")
    vol_mult = DecimalParameter(1.2, 2.5, decimals=2, default=1.5, space="buy")

    # Volatilitetsstyrd position sizing (hyperoptbar)
    risk_per_trade = DecimalParameter(0.002, 0.02, decimals=3, default=0.010, space="buy")
    atr_stop_mult = DecimalParameter(1.5, 4.0, decimals=1, default=2.0, space="buy")
    max_stake_pct = DecimalParameter(0.02, 0.20, decimals=2, default=0.10, space="buy")

    plot_config = {
        "main_plot": {
            "bb_upper": {},
            "bb_lower": {},
            "bb_mid": {},
        },
        "subplots": {
            "ATR": {"atr": {}},
            "BBWidth": {"bb_width": {}, "bb_width_min": {}},
        },
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        df = dataframe.sort_index()

        # Bollinger bands + width
        win = int(self.bb_window.value)
        sma = df["close"].rolling(win, min_periods=win).mean()
        std = df["close"].rolling(win, min_periods=win).std(ddof=0)
        df["bb_mid"] = sma
        df["bb_upper"] = sma + 2.0 * std
        df["bb_lower"] = sma - 2.0 * std
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma

        # Squeeze: rullande minimalt band-bredd
        sq_lb = int(self.squeeze_lb.value)
        df["bb_width_min"] = df["bb_width"].rolling(sq_lb, min_periods=sq_lb).min()

        # ATR för risk/plot
        atr_n = 14
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_n, min_periods=atr_n).mean()

        # Volymmedel
        df["volume_mean"] = df["volume"].rolling(window=20, min_periods=20).mean()

        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        df = dataframe.copy()
        width_min = df["bb_width_min"].fillna(method="ffill")
        df["enter_long"] = (
            (df["close"] > df["bb_upper"]) &
            (df["bb_width"] > float(self.bb_min_width.value)) &
            (df["bb_width"] > width_min * float(self.width_expansion_mult.value)) &
            (df["volume"] > df["volume_mean"] * float(self.vol_mult.value)) &
            (df["volume_mean"].fillna(0) > 0)
        )
        df.loc[df["enter_long"], ["enter_long", "enter_tag"]] = (1, "bb_breakout")
        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        df = dataframe.copy()
        # Exit på mean-reversion eller momentum-avtagande; trailing tar vinster
        df["exit_long"] = (
            (df["close"] < df["bb_mid"]) &
            (df["volume"] > 0)
        )
        df.loc[df["exit_long"], ["exit_long", "exit_tag"]] = (1, "bb_revert")
        return df

    # --- Risk/position sizing ---
    def custom_stake_amount(
        self,
        pair: str,
        current_time,  # datetime
        current_rate: float,
        current_profit: float,
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
