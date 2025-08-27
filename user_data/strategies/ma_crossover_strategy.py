from __future__ import annotations

from decimal import Decimal

import pandas as pd
from freqtrade.strategy import DecimalParameter, IntParameter
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
    minimal_roi: dict[str, float] = {"0": 0.03}
    stoploss: float = -0.10

    # Trailing-stop (aktivera enkel positiv trailing för att låsa vinst)
    trailing_stop: bool = True
    trailing_stop_positive: float = 0.01
    trailing_stop_positive_offset: float = 0.03
    trailing_only_offset_is_reached: bool = True

    # Hyperoptbara parametrar
    ema_short = IntParameter(5, 50, default=12, space="buy")
    ema_long = IntParameter(20, 200, default=26, space="buy")

    # Filterparametrar enligt analys: RSI och Bollinger Band-width
    rsi_length = IntParameter(7, 21, default=14, space="buy")
    rsi_buy = IntParameter(50, 60, default=52, space="buy")
    bb_window = IntParameter(14, 40, default=20, space="buy")
    bb_min_width = DecimalParameter(0.010, 0.060, decimals=3, default=0.020, space="buy")

    # Visualisering för snabb validering
    plot_config = {
        "main_plot": {
            "ema_short": {},
            "ema_long": {},
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
    risk_per_trade = DecimalParameter(0.002, 0.02, decimals=3, default=0.010, space="buy")
    atr_stop_mult = DecimalParameter(1.5, 4.0, decimals=1, default=2.0, space="buy")
    max_stake_pct = DecimalParameter(0.02, 0.20, decimals=2, default=0.10, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Säkerställ sorterad data
        df = dataframe.sort_index()

        # EMA-beräkningar (utan externa beroenden)
        df["ema_short"] = df["close"].ewm(span=int(self.ema_short.value), adjust=False).mean()
        df["ema_long"] = df["close"].ewm(span=int(self.ema_long.value), adjust=False).mean()

        # Volymfilter (enkel)
        df["volume_mean"] = df["volume"].rolling(window=20, min_periods=20).mean()

        # MACD (12/26/9)
        df["macd_fast"] = df["close"].ewm(span=12, adjust=False).mean()
        df["macd_slow"] = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = df["macd_fast"] - df["macd_slow"]
        df["macdsignal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macdhist"] = df["macd"] - df["macdsignal"]

        # RSI (utan externa paket)
        rsi_len = int(self.rsi_length.value)
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=rsi_len, min_periods=rsi_len).mean()
        avg_loss = loss.rolling(window=rsi_len, min_periods=rsi_len).mean()
        rs = avg_gain / (avg_loss.replace(0, 1e-10))
        df["rsi"] = 100 - (100 / (1 + rs))

        # Bollinger Bands och width
        bb_win = int(self.bb_window.value)
        sma = df["close"].rolling(bb_win, min_periods=bb_win).mean()
        std = df["close"].rolling(bb_win, min_periods=bb_win).std(ddof=0)
        df["bb_upper"] = sma + 2.0 * std
        df["bb_lower"] = sma - 2.0 * std
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma

        # ATR (14) – för analys/plot och ev. framtida position sizing
        atr_n = 14
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_n, min_periods=atr_n).mean()

        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        df["enter_long"] = (
            (df["ema_short"] > df["ema_long"]) &
            (df["macdhist"] > 0) &
            (df["rsi"] > int(self.rsi_buy.value)) &
            (df["bb_width"] > float(self.bb_min_width.value)) &
            (df["volume"] > 0) &
            (df["volume_mean"].fillna(0) > 0)
        )

        df.loc[df["enter_long"], "enter_tag"] = "ema_crossover+filters"
        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        df["exit_long"] = (
            ((df["ema_short"] < df["ema_long"]) | (df["macdhist"] < 0)) &
            (df["volume"] > 0)
        )

        df.loc[df["exit_long"], "exit_tag"] = "ema_crossdown"
        return df

    # --- Risk/position sizing ---
    def custom_stake_amount(
        self,
        pair: str,
        current_time,  # datetime
        current_rate: float,
        **kwargs,
    ) -> float | None:
        """ATR-baserad position sizing.

        Beräknar stake i stake-valutan baserat på önskad risk per trade och
        stop distance = ATR * multiplikator. Om data saknas eller är orimlig
        returneras None för att använda default stake.
        """
        # Skydd: kräver dp/wallets i runtime (ej vid import/test)
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
        # Rimlighetskontroll på stop_fraction
        if not (0.001 <= stop_fraction <= 0.2):
            return None

        # Hämta tillgängligt kapital i stake-valutan
        free_stake = None
        try:
            if hasattr(self, "wallets") and self.wallets:
                free_stake = float(self.wallets.get_free(self.stake_currency))
        except Exception:
            free_stake = None

        # Riskbelopp = free_stake * risk_per_trade
        risk_frac = float(self.risk_per_trade.value)
        if free_stake is None or free_stake <= 0:
            # Fallback: använd current_rate som approximativ referens; returnera None om orimligt
            return None

        risk_amount = free_stake * risk_frac
        if risk_amount <= 0:
            return None

        # Stake beräknas som risk / stop_fraction, begränsa till max_stake_pct av free
        raw_stake = risk_amount / max(stop_fraction, 1e-9)
        max_stake = free_stake * float(self.max_stake_pct.value)
        stake = max(0.0, min(raw_stake, max_stake))

        # Säkerhetsgolv: kräver minst en liten summa; annars None -> default
        if stake < 10:  # antag USDT-miljö; lågt golv för att undvika micro-orders
            return None

        # Använd Decimal internt för numerisk korrekthet, returnera float till Freqtrade
        return float(Decimal(stake).quantize(Decimal("0.01")))
