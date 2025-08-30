"""Factor analysis framework for market drivers."""


import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from app.strategies.utils import get_json_logger

logger = get_json_logger("factor_analysis")


class FactorConfig(BaseModel):
    """Factor analysis configuration."""

    num_factors: int = 5
    min_variance_explained: float = 0.8
    lookback_period: int = 252
    correlation_threshold: float = 0.7
    factor_categories: list[str] = ["macro", "market", "technical", "sentiment"]


class MarketFactor:
    """Individual market factor."""

    def __init__(self, name: str, category: str):
        """Initialize market factor."""
        self.name = name
        self.category = category
        self.data = None
        self.weight = 0.0
        self.importance_score = 0.0

    def calculate(self, market_data: pd.DataFrame) -> pd.Series:
        """Calculate factor values from market data."""
        raise NotImplementedError("Subclasses must implement calculate()")


class MacroFactors:
    """Macroeconomic factors."""

    @staticmethod
    def interest_rate_factor(rates_data: pd.Series) -> pd.Series:
        """Interest rate change factor."""
        return rates_data.pct_change()

    @staticmethod
    def inflation_factor(cpi_data: pd.Series) -> pd.Series:
        """Inflation expectation factor."""
        return cpi_data.pct_change(12)  # YoY change

    @staticmethod
    def dollar_strength_factor(dxy_data: pd.Series) -> pd.Series:
        """Dollar index strength factor."""
        return dxy_data.pct_change()

    @staticmethod
    def commodity_factor(commodity_index: pd.Series) -> pd.Series:
        """Commodity price factor."""
        return commodity_index.pct_change()


class MarketFactors:
    """Market-specific factors."""

    @staticmethod
    def momentum_factor(prices: pd.DataFrame) -> pd.Series:
        """Cross-sectional momentum factor."""
        returns = prices.pct_change(20)  # 20-day momentum
        return returns.mean(axis=1)

    @staticmethod
    def volatility_factor(prices: pd.DataFrame) -> pd.Series:
        """Market volatility factor."""
        returns = prices.pct_change()
        return returns.std(axis=1)

    @staticmethod
    def liquidity_factor(volumes: pd.DataFrame, prices: pd.DataFrame) -> pd.Series:
        """Market liquidity factor."""
        dollar_volume = volumes * prices
        return dollar_volume.mean(axis=1)

    @staticmethod
    def correlation_factor(returns: pd.DataFrame, window: int = 60) -> pd.Series:
        """Average pairwise correlation factor."""
        rolling_corr = returns.rolling(window).corr().mean()
        return rolling_corr.mean(level=0)


class TechnicalFactors:
    """Technical analysis factors."""

    @staticmethod
    def trend_strength_factor(prices: pd.DataFrame, period: int = 50) -> pd.Series:
        """Trend strength across assets."""
        sma = prices.rolling(period).mean()
        distance = (prices - sma) / sma
        return distance.mean(axis=1)

    @staticmethod
    def mean_reversion_factor(prices: pd.DataFrame, period: int = 20) -> pd.Series:
        """Mean reversion factor."""
        sma = prices.rolling(period).mean()
        z_scores = (prices - sma) / prices.rolling(period).std()
        return -z_scores.mean(axis=1)  # Negative for reversion

    @staticmethod
    def breakout_factor(prices: pd.DataFrame, period: int = 20) -> pd.Series:
        """Breakout strength factor."""
        high = prices.rolling(period).max()
        low = prices.rolling(period).min()
        breakout = ((prices - high.shift(1)) / high.shift(1)).fillna(0)
        breakdown = ((low.shift(1) - prices) / low.shift(1)).fillna(0)
        return breakout.mean(axis=1) - breakdown.mean(axis=1)


class FactorAnalyzer:
    """Analyze and combine market factors."""

    def __init__(self, config: FactorConfig = None):
        """Initialize factor analyzer."""
        self.config = config or FactorConfig()
        self.factors = {}
        self.factor_loadings = None
        self.scaler = StandardScaler()

    def add_factor(self, name: str, data: pd.Series, category: str = "custom"):
        """Add a factor to the analysis."""
        factor = MarketFactor(name, category)
        factor.data = data
        self.factors[name] = factor

        logger.info(f"Added factor: {name} ({category})")

    def run_pca(self) -> tuple[np.ndarray, np.ndarray]:
        """Run PCA on factors."""
        if not self.factors:
            return None, None

        # Prepare factor matrix
        factor_data = pd.DataFrame({name: factor.data for name, factor in self.factors.items()})

        # Handle missing values
        factor_data = factor_data.fillna(method="ffill").fillna(0)

        # Standardize
        factor_data_scaled = self.scaler.fit_transform(factor_data)

        # Run PCA
        pca = PCA(n_components=min(self.config.num_factors, len(self.factors)))
        principal_components = pca.fit_transform(factor_data_scaled)

        # Store loadings
        self.factor_loadings = pd.DataFrame(
            pca.components_.T,
            columns=[f"PC{i+1}" for i in range(pca.n_components_)],
            index=factor_data.columns,
        )

        logger.info(f"PCA explained variance: {pca.explained_variance_ratio_}")

        return principal_components, pca.explained_variance_ratio_

    def identify_key_factors(self) -> list[str]:
        """Identify most important factors."""
        if self.factor_loadings is None:
            self.run_pca()

        if self.factor_loadings is None:
            return []

        # Calculate importance scores
        importance_scores = {}

        for factor_name in self.factor_loadings.index:
            # Sum of absolute loadings weighted by explained variance
            score = 0
            for i, pc in enumerate(self.factor_loadings.columns):
                loading = abs(self.factor_loadings.loc[factor_name, pc])
                # Weight by explained variance (would need to store from PCA)
                score += loading

            importance_scores[factor_name] = score

        # Sort and return top factors
        sorted_factors = sorted(importance_scores.items(), key=lambda x: x[1], reverse=True)

        # Update factor importance scores
        for name, score in importance_scores.items():
            if name in self.factors:
                self.factors[name].importance_score = score

        return [f[0] for f in sorted_factors[:5]]

    def calculate_factor_exposures(self, asset_returns: pd.Series) -> dict[str, float]:
        """Calculate asset's exposure to each factor."""
        exposures = {}

        for name, factor in self.factors.items():
            if factor.data is not None:
                # Calculate correlation as exposure
                correlation = asset_returns.corr(factor.data)
                exposures[name] = correlation

        return exposures

    def build_factor_model(self, asset_returns: pd.DataFrame) -> dict:
        """Build multi-factor model for assets."""
        if not self.factors:
            return {}

        # Prepare data
        factor_data = pd.DataFrame({name: factor.data for name, factor in self.factors.items()})

        # Align data
        aligned_data = pd.concat([asset_returns, factor_data], axis=1).dropna()

        # Run regression for each asset
        models = {}

        for asset in asset_returns.columns:
            # Multiple linear regression
            y = aligned_data[asset].values
            X = aligned_data[list(self.factors.keys())].values

            # Add constant
            X = np.column_stack([np.ones(len(X)), X])

            # OLS regression
            coeffs = np.linalg.lstsq(X, y, rcond=None)[0]

            models[asset] = {
                "alpha": coeffs[0],
                "betas": {name: coeffs[i + 1] for i, name in enumerate(self.factors.keys())},
                "r_squared": self._calculate_r_squared(y, X @ coeffs),
            }

        return models

    def _calculate_r_squared(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate R-squared."""
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)

        if ss_tot > 0:
            return 1 - (ss_res / ss_tot)
        return 0.0


class FactorRotation:
    """Rotate between factors based on regime."""

    def __init__(self, analyzer: FactorAnalyzer):
        """Initialize factor rotation."""
        self.analyzer = analyzer
        self.rotation_history = []

    def get_factor_weights(self, market_regime: str) -> dict[str, float]:
        """Get factor weights for current regime."""
        weights = {}

        if market_regime == "bull":
            # Overweight momentum and trend
            weights = {"momentum": 0.4, "trend": 0.3, "volatility": -0.2, "mean_reversion": -0.1}
        elif market_regime == "bear":
            # Defensive factors
            weights = {"volatility": 0.3, "mean_reversion": 0.3, "momentum": -0.2, "trend": -0.2}
        elif market_regime == "sideways":
            # Range-bound factors
            weights = {"mean_reversion": 0.5, "volatility": 0.2, "momentum": -0.2, "trend": -0.1}
        else:  # volatile
            weights = {"volatility": 0.5, "mean_reversion": 0.2, "momentum": -0.2, "trend": -0.1}

        # Normalize weights
        total = sum(abs(v) for v in weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def calculate_factor_score(
        self, factor_values: dict[str, float], weights: dict[str, float]
    ) -> float:
        """Calculate composite factor score."""
        score = 0.0

        for factor, value in factor_values.items():
            if factor in weights:
                score += value * weights[factor]

        return score

    def generate_signals(self, factor_scores: pd.Series, threshold: float = 0.5) -> pd.Series:
        """Generate trading signals from factor scores."""
        signals = pd.Series(index=factor_scores.index, data=0)

        # Long when score > threshold
        signals[factor_scores > threshold] = 1

        # Short when score < -threshold
        signals[factor_scores < -threshold] = -1

        return signals
