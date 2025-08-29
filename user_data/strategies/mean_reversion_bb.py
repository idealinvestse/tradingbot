from __future__ import annotations

from decimal import Decimal
import os

import pandas as pd
from freqtrade.strategy import DecimalParameter, IntParameter
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
from app.strategies.logging_utils import get_json_logger
from app.adapters.onchain.web3_adapter import OnchainClient, Web3Config


class MeanReversionBbStrategy(IStrategy):
    """Mean-reversion strategi med Bollinger Bands och RSI.

    Hypotes:
    - Köp när priset devierar nedåt (under BB-lower) i en sidledes/regim med låg volatilitet,
      och RSI signalerar översålt.
    - Sälj när priset revertar mot medel (SMA/BB-mid) eller momentum avtar.
    """

    timeframe: str = "5m"
    startup_candle_count: int = 200
    process_only_new_candles: bool = True

    # Konservativ ROI/SL (optimeras via hyperopt)
    minimal_roi: dict[str, float] = {
        "0": 0.03,
        "60": 0.02,
        "180": 0.0,
    }
    stoploss: float = -0.08

    trailing_stop: bool = True
    trailing_stop_positive: float = 0.01
    trailing_stop_positive_offset: float = 0.02
    trailing_only_offset_is_reached: bool = True

    # Hyperoptbara parametrar (köp/sälj-filter)
    bb_window = IntParameter(14, 40, default=20, space="buy")
    bb_std_mult = DecimalParameter(1.5, 3.0, decimals=1, default=2.0, space="buy")
    rsi_buy = IntParameter(20, 35, default=30, space="buy")
    rsi_exit = IntParameter(40, 55, default=45, space="sell")
    bb_width_max = DecimalParameter(0.02, 0.10, decimals=3, default=0.050, space="buy")

    # Volatilitetsstyrd position sizing (hyperoptbar)
    risk_per_trade = DecimalParameter(0.002, 0.02, decimals=3, default=0.008, space="buy")
    atr_stop_mult = DecimalParameter(1.5, 3.0, decimals=1, default=2.0, space="buy")
    max_stake_pct = DecimalParameter(0.02, 0.20, decimals=2, default=0.06, space="buy")

    plot_config = {
        "main_plot": {
            "bb_upper": {},
            "bb_lower": {},
        },
        "subplots": {
            "RSI": {"rsi": {}},
            "BBWidth": {"bb_width": {}},
            "ATR": {"atr": {}},
        },
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.sort_index()

        # Bollinger Bands + width
        win = int(self.bb_window.value)
        std_mult = float(self.bb_std_mult.value)
        sma = df["close"].rolling(win, min_periods=win).mean()
        std = df["close"].rolling(win, min_periods=win).std(ddof=0)
        df["bb_upper"] = sma + std_mult * std
        df["bb_lower"] = sma - std_mult * std
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma

        # RSI
        rsi_len = 14
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=rsi_len, min_periods=rsi_len).mean()
        avg_loss = loss.rolling(window=rsi_len, min_periods=rsi_len).mean()
        rs = avg_gain / (avg_loss.replace(0, 1e-10))
        df["rsi"] = 100 - (100 / (1 + rs))

        # ATR (14)
        atr_n = 14
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_n, min_periods=atr_n).mean()

        # Volymmedel
        df["volume_mean"] = df["volume"].rolling(window=20, min_periods=20).mean()
        # Live/Dry-run: enrich med senaste pris via DataProvider (fail-safe)
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

        # On-chain (valfritt via env FEATURE_ONCHAIN)
        try:
            if os.getenv("FEATURE_ONCHAIN", "").strip().lower() in {"1", "true", "yes"}:
                address = os.getenv("ONCHAIN_ADDRESS")
                if address:
                    logger = get_json_logger(
                        "strategy",
                        static_fields={
                            "strategy": self.__class__.__name__,
                            "timeframe": self.timeframe,
                            "pair": (metadata or {}).get("pair"),
                            "feature": "onchain",
                        },
                    )
                    try:
                        # Initiera klient och hämta enkel metrik
                        cfg = Web3Config()
                        client = OnchainClient(cfg=cfg)
                        txc = client.get_tx_count(address)
                        # Sätt samma värde över hela DF för enkelhet
                        df["wallet_activity"] = txc
                        logger.info("onchain_tx_count", extra={"address": address, "tx_count": int(txc)})
                    except Exception as e:  # noqa: BLE001
                        logger.warning("onchain_error", extra={"error": str(e)})
        except Exception:
            pass

        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        df["enter_long"] = (
            (df["close"] < df["bb_lower"]) &
            (df["rsi"] < int(self.rsi_buy.value)) &
            (df["bb_width"] < float(self.bb_width_max.value)) &
            (df["volume"] > 0) & (df["volume_mean"].fillna(0) > 0)
        )
        df.loc[df["enter_long"], "enter_tag"] = "meanrev_bb"
        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        # Exit på revert mot mittband eller RSI normaliseras
        win = int(self.bb_window.value)
        mid = df["close"].rolling(win, min_periods=win).mean()
        df["exit_long"] = (
            ((df["close"] >= mid) | (df["rsi"] > int(self.rsi_exit.value))) &
            (df["volume"] > 0)
        )
        df.loc[df["exit_long"], "exit_tag"] = "meanrev_tp"
        return df

    # --- Risk/position sizing ---
    def custom_stake_amount(
        self,
        pair: str,
        current_time,  # datetime
        current_rate: float,
        **kwargs,
    ) -> float | None:
        """ATR-baserad position sizing."""
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
