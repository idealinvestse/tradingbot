from __future__ import annotations

from decimal import Decimal

import pandas as pd
from freqtrade.strategy import DecimalParameter, IntParameter
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
from app.strategies.logging_utils import get_json_logger


class MomentumMacdRsiStrategy(IStrategy):
    """Momentum-strategi baserad på MACD + RSI med BB-width expansionsfilter.

    Hypotes:
    - Gå lång när momentum växlar positivt (MACD-hist > 0 och stigande)
      samtidigt som marknaden visar styrka (RSI > tröskel) och expanderande volatilitet
      (Bollinger width över miniminivå).

    Exits:
    - Momentum avtar (MACD-hist < 0) eller RSI < 50; trailing tar vinst.
    """

    timeframe: str = "5m"
    startup_candle_count: int = 200
    process_only_new_candles: bool = True

    minimal_roi: dict[str, float] = {
        "0": 0.184,
        "37": 0.056,
        "88": 0.04,
        "157": 0,
    }
    stoploss: float = -0.28

    trailing_stop: bool = True
    trailing_stop_positive: float = 0.01
    trailing_stop_positive_offset: float = 0.03
    trailing_only_offset_is_reached: bool = True

    # Hyperoptbara filterparametrar
    rsi_length = IntParameter(7, 21, default=16, space="buy")
    rsi_buy = IntParameter(50, 60, default=60, space="buy")
    bb_window = IntParameter(14, 40, default=31, space="buy")
    bb_min_width = DecimalParameter(0.010, 0.060, decimals=3, default=0.058, space="buy")

    plot_config = {
        "main_plot": {
            "bb_upper": {},
            "bb_lower": {},
        },
        "subplots": {
            "MACD": {"macd": {}, "macdsignal": {}, "macdhist": {}},
            "RSI": {"rsi": {}},
            "ATR": {"atr": {}},
            "BBWidth": {"bb_width": {}},
        },
    }

    # Volatilitetsstyrd position sizing (hyperoptbar)
    risk_per_trade = DecimalParameter(0.002, 0.02, decimals=3, default=0.009, space="buy")
    atr_stop_mult = DecimalParameter(1.5, 4.0, decimals=1, default=2.4, space="buy")
    max_stake_pct = DecimalParameter(0.02, 0.20, decimals=2, default=0.07, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.sort_index()

        # MACD (12/26/9)
        df["macd_fast"] = df["close"].ewm(span=12, adjust=False).mean()
        df["macd_slow"] = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = df["macd_fast"] - df["macd_slow"]
        df["macdsignal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macdhist"] = df["macd"] - df["macdsignal"]

        # RSI
        rsi_len = int(self.rsi_length.value)
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=rsi_len, min_periods=rsi_len).mean()
        avg_loss = loss.rolling(window=rsi_len, min_periods=rsi_len).mean()
        rs = avg_gain / (avg_loss.replace(0, 1e-10))
        df["rsi"] = 100 - (100 / (1 + rs))

        # Bollinger Bands + width
        bb_win = int(self.bb_window.value)
        sma = df["close"].rolling(bb_win, min_periods=bb_win).mean()
        std = df["close"].rolling(bb_win, min_periods=bb_win).std(ddof=0)
        df["bb_upper"] = sma + 2.0 * std
        df["bb_lower"] = sma - 2.0 * std
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma

        # ATR (14)
        atr_n = 14
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_n, min_periods=atr_n).mean()

        # Volymmedel
        df["volume_mean"] = df["volume"].rolling(window=20, min_periods=20).mean()

        # Live/Dry-run: enrich med senaste pris via DataProvider, fail-safe vid fel
        try:
            if hasattr(self, "dp") and self.dp is not None and getattr(self.dp, "runmode", None):
                rm = getattr(self.dp.runmode, "value", str(self.dp.runmode))
                if rm in ("live", "dry_run"):
                    logger = get_json_logger(
                        "strategy",
                        static_fields={
                            "strategy": self.__class__.__name__,
                            "timeframe": self.timeframe,
                            "pair": (metadata or {}).get("pair"),
                            "runmode": rm,
                        },
                    )
                    pair = (metadata or {}).get("pair")
                    try:
                        ticker = self.dp.ticker(pair) if pair else None
                        if ticker:
                            last = (
                                ticker.get("last")
                                or ticker.get("last_price")
                                or ticker.get("close")
                                or 0
                            )
                            df["last_price"] = last
                            logger.debug("ticker_fetched", extra={"source": "dp.ticker"})
                        else:
                            df["last_price"] = 0
                            logger.warning("ticker_missing", extra={"reason": "empty_or_no_pair"})
                    except Exception as e:  # noqa: BLE001
                        df["last_price"] = 0
                        logger.error("dp_ticker_error", extra={"error": str(e)})
        except Exception:
            pass

        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        df["enter_long"] = (
            (df["macdhist"] > 0) &
            (df["macdhist"] > df["macdhist"].shift(1)) &
            (df["rsi"] > int(self.rsi_buy.value)) &
            (df["bb_width"] > float(self.bb_min_width.value)) &
            (df["volume"] > 0) &
            (df["volume_mean"].fillna(0) > 0)
        )
        df.loc[df["enter_long"], "enter_tag"] = "mom_macd_rsi"

        # Logga entry-signaler i live/dry_run
        try:
            if hasattr(self, "dp") and self.dp is not None and getattr(self.dp, "runmode", None):
                rm = getattr(self.dp.runmode, "value", str(self.dp.runmode))
                if rm in ("live", "dry_run"):
                    logger = get_json_logger(
                        "strategy",
                        static_fields={
                            "strategy": self.__class__.__name__,
                            "timeframe": self.timeframe,
                            "pair": (metadata or {}).get("pair"),
                            "runmode": rm,
                        },
                    )
                    cnt = int(df.get("enter_long", pd.Series(dtype=bool)).sum())
                    if cnt:
                        logger.info("entry_signals", extra={"count": cnt})
        except Exception:
            pass
        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        df["exit_long"] = (
            ((df["macdhist"] < 0) | (df["rsi"] < 50)) &
            (df["volume"] > 0)
        )
        df.loc[df["exit_long"], "exit_tag"] = "mom_loss_momentum"

        # Logga exit-signaler i live/dry_run
        try:
            if hasattr(self, "dp") and self.dp is not None and getattr(self.dp, "runmode", None):
                rm = getattr(self.dp.runmode, "value", str(self.dp.runmode))
                if rm in ("live", "dry_run"):
                    logger = get_json_logger(
                        "strategy",
                        static_fields={
                            "strategy": self.__class__.__name__,
                            "timeframe": self.timeframe,
                            "pair": (metadata or {}).get("pair"),
                            "runmode": rm,
                        },
                    )
                    cnt = int(df.get("exit_long", pd.Series(dtype=bool)).sum())
                    if cnt:
                        logger.info("exit_signals", extra={"count": cnt})
        except Exception:
            pass
        return df

    # --- Risk/position sizing ---
    def custom_stake_amount(
        self,
        pair: str,
        current_time,  # datetime
        current_rate: float,
        **kwargs,
    ) -> float | None:
        """ATR-baserad position sizing (samma logik som i MaCrossoverStrategy)."""
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

        risk_frac = float(self.risk_per_trade.value)
        if free_stake is None or free_stake <= 0:
            return None

        risk_amount = free_stake * risk_frac
        if risk_amount <= 0:
            return None

        raw_stake = risk_amount / max(stop_fraction, 1e-9)
        max_stake = free_stake * float(self.max_stake_pct.value)
        stake = max(0.0, min(raw_stake, max_stake))

        if stake < 10:
            return None

        return float(Decimal(stake).quantize(Decimal("0.01")))
