"""Pairs trading statistical arbitrage module."""


import numpy as np
import pandas as pd
from pydantic import BaseModel
from statsmodels.tsa.stattools import coint

from app.strategies.utils import get_json_logger

logger = get_json_logger("pairs_trading")


class PairsConfig(BaseModel):
    """Pairs trading configuration."""

    lookback_period: int = 60
    zscore_entry: float = 2.0
    zscore_exit: float = 0.5
    min_correlation: float = 0.8
    max_half_life: int = 30
    cointegration_pvalue: float = 0.05


class PairAnalyzer:
    """Analyze pairs for trading opportunities."""

    def __init__(self, config: PairsConfig = None):
        """Initialize pair analyzer."""
        self.config = config or PairsConfig()
        self.pairs_data = {}

    def find_cointegrated_pairs(
        self, data: dict[str, pd.DataFrame]
    ) -> list[tuple[str, str, float]]:
        """Find cointegrated pairs from price data."""
        symbols = list(data.keys())
        cointegrated_pairs = []

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                symbol1, symbol2 = symbols[i], symbols[j]

                # Get price series
                price1 = data[symbol1]["close"]
                price2 = data[symbol2]["close"]

                # Check cointegration
                score, pvalue, _ = coint(price1, price2)

                if pvalue < self.config.cointegration_pvalue:
                    # Check correlation
                    correlation = price1.corr(price2)

                    if correlation > self.config.min_correlation:
                        cointegrated_pairs.append((symbol1, symbol2, pvalue))
                        logger.info(
                            f"Found cointegrated pair: {symbol1}-{symbol2}, p-value: {pvalue:.4f}"
                        )

        return cointegrated_pairs

    def calculate_spread(self, price1: pd.Series, price2: pd.Series) -> pd.Series:
        """Calculate spread between two price series."""
        # Use log prices for better statistical properties
        log_price1 = np.log(price1)
        log_price2 = np.log(price2)

        # Calculate hedge ratio using OLS
        hedge_ratio = self._calculate_hedge_ratio(log_price1, log_price2)

        # Calculate spread
        spread = log_price1 - hedge_ratio * log_price2

        return spread

    def _calculate_hedge_ratio(self, series1: pd.Series, series2: pd.Series) -> float:
        """Calculate hedge ratio using OLS regression."""
        # Simple linear regression
        x = series2.values.reshape(-1, 1)
        y = series1.values

        # Add constant
        x = np.column_stack([np.ones(len(x)), x])

        # OLS estimation
        coeffs = np.linalg.lstsq(x, y, rcond=None)[0]

        return coeffs[1]

    def calculate_zscore(self, spread: pd.Series, window: int = None) -> pd.Series:
        """Calculate z-score of spread."""
        window = window or self.config.lookback_period

        spread_mean = spread.rolling(window).mean()
        spread_std = spread.rolling(window).std()

        zscore = (spread - spread_mean) / spread_std

        return zscore

    def calculate_half_life(self, spread: pd.Series) -> int:
        """Calculate mean reversion half-life."""
        # Use OLS to estimate mean reversion speed
        spread_lag = spread.shift(1)
        spread_diff = spread - spread_lag

        # Remove NaN values
        spread_lag = spread_lag.dropna()
        spread_diff = spread_diff.dropna()

        # Align indices
        common_index = spread_lag.index.intersection(spread_diff.index)
        spread_lag = spread_lag.loc[common_index]
        spread_diff = spread_diff.loc[common_index]

        # OLS regression
        x = spread_lag.values.reshape(-1, 1)
        y = spread_diff.values

        if len(x) > 0:
            coeffs = np.linalg.lstsq(x, y, rcond=None)[0]
            lambda_param = -coeffs[0]

            if lambda_param > 0:
                half_life = int(np.log(2) / lambda_param)
                return min(half_life, 365)  # Cap at 1 year

        return self.config.max_half_life


class PairsTradingStrategy:
    """Execute pairs trading strategy."""

    def __init__(self, pair: tuple[str, str], config: PairsConfig = None):
        """Initialize pairs trading strategy."""
        self.pair = pair
        self.config = config or PairsConfig()
        self.analyzer = PairAnalyzer(config)
        self.position = 0  # -1: short spread, 0: no position, 1: long spread
        self.entry_zscore = None

    def generate_signals(self, price1: pd.Series, price2: pd.Series) -> pd.Series:
        """Generate trading signals."""
        # Calculate spread and z-score
        spread = self.analyzer.calculate_spread(price1, price2)
        zscore = self.analyzer.calculate_zscore(spread)

        # Calculate half-life
        half_life = self.analyzer.calculate_half_life(spread)

        if half_life > self.config.max_half_life:
            logger.warning(f"Half-life too long: {half_life} days")
            return pd.Series(0, index=zscore.index)  # No trading

        # Generate signals
        signals = pd.Series(0, index=zscore.index)

        for i in range(1, len(zscore)):
            if pd.isna(zscore.iloc[i]):
                continue

            current_z = zscore.iloc[i]

            if self.position == 0:
                # Entry signals
                if current_z > self.config.zscore_entry:
                    signals.iloc[i] = -1  # Short spread
                    self.position = -1
                    self.entry_zscore = current_z
                elif current_z < -self.config.zscore_entry:
                    signals.iloc[i] = 1  # Long spread
                    self.position = 1
                    self.entry_zscore = current_z

            elif self.position != 0:
                # Exit signals
                if abs(current_z) < self.config.zscore_exit:
                    signals.iloc[i] = -self.position  # Close position
                    self.position = 0
                    self.entry_zscore = None
                # Stop loss: if z-score moves further against us
                elif self.position == 1 and current_z < self.entry_zscore - 1:
                    signals.iloc[i] = -1  # Close long
                    self.position = 0
                    self.entry_zscore = None
                elif self.position == -1 and current_z > self.entry_zscore + 1:
                    signals.iloc[i] = 1  # Close short
                    self.position = 0
                    self.entry_zscore = None

        return signals

    def calculate_position_sizes(
        self, capital: float, price1: float, price2: float, hedge_ratio: float
    ) -> tuple[float, float]:
        """Calculate position sizes for each leg."""
        # Allocate capital based on hedge ratio
        total_allocation = capital

        # Position in asset 1
        position1_value = total_allocation / (1 + abs(hedge_ratio))
        position1_shares = position1_value / price1

        # Position in asset 2
        position2_value = total_allocation * abs(hedge_ratio) / (1 + abs(hedge_ratio))
        position2_shares = position2_value / price2

        return position1_shares, position2_shares


class PairsPortfolio:
    """Manage portfolio of pairs trades."""

    def __init__(self, pairs: list[tuple[str, str]], capital: float):
        """Initialize pairs portfolio."""
        self.pairs = pairs
        self.capital = capital
        self.strategies = {}
        self.positions = {}

        # Initialize strategies for each pair
        for pair in pairs:
            self.strategies[pair] = PairsTradingStrategy(pair)
            self.positions[pair] = {"asset1": 0, "asset2": 0}

    def update_signals(self, market_data: dict[str, pd.DataFrame]) -> dict:
        """Update signals for all pairs."""
        signals = {}

        capital_per_pair = self.capital / len(self.pairs)

        for pair in self.pairs:
            asset1, asset2 = pair

            if asset1 in market_data and asset2 in market_data:
                price1 = market_data[asset1]["close"]
                price2 = market_data[asset2]["close"]

                # Generate signals
                pair_signals = self.strategies[pair].generate_signals(price1, price2)

                # Calculate positions
                if pair_signals.iloc[-1] != 0:
                    current_price1 = price1.iloc[-1]
                    current_price2 = price2.iloc[-1]

                    analyzer = PairAnalyzer()
                    hedge_ratio = analyzer._calculate_hedge_ratio(np.log(price1), np.log(price2))

                    pos1, pos2 = self.strategies[pair].calculate_position_sizes(
                        capital_per_pair, current_price1, current_price2, hedge_ratio
                    )

                    signal_value = pair_signals.iloc[-1]

                    signals[pair] = {
                        "signal": signal_value,
                        "positions": {
                            asset1: pos1 * signal_value,
                            asset2: -pos2 * signal_value,  # Opposite position
                        },
                    }

        return signals

    def calculate_performance(self, market_data: dict[str, pd.DataFrame]) -> dict:
        """Calculate portfolio performance metrics."""
        total_pnl = 0
        pair_performances = {}

        for pair in self.pairs:
            asset1, asset2 = pair

            if asset1 in market_data and asset2 in market_data:
                # Calculate PnL for this pair
                pos1 = self.positions[pair]["asset1"]
                pos2 = self.positions[pair]["asset2"]

                price1_change = market_data[asset1]["close"].pct_change().iloc[-1]
                price2_change = market_data[asset2]["close"].pct_change().iloc[-1]

                pair_pnl = pos1 * price1_change + pos2 * price2_change

                pair_performances[pair] = {"pnl": pair_pnl, "position1": pos1, "position2": pos2}

                total_pnl += pair_pnl

        return {
            "total_pnl": total_pnl,
            "pair_performances": pair_performances,
            "return": total_pnl / self.capital if self.capital > 0 else 0,
        }
