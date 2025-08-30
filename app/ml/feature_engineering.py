"""Feature engineering pipeline for market data."""


import numpy as np
import pandas as pd
import talib
from pydantic import BaseModel
from sklearn.preprocessing import StandardScaler

from app.strategies.utils import get_json_logger

logger = get_json_logger("feature_engineering")


class FeatureConfig(BaseModel):
    """Feature engineering configuration."""

    technical_indicators: list[str] = ["RSI", "MACD", "BB", "ATR", "ADX", "OBV"]
    price_features: list[str] = ["returns", "log_returns", "volatility", "volume_ratio"]
    window_sizes: list[int] = [5, 10, 20, 50]
    normalize: bool = True
    handle_missing: str = "forward_fill"  # forward_fill, backward_fill, interpolate, drop


class FeatureEngineer:
    """Feature engineering for trading strategies."""

    def __init__(self, config: FeatureConfig = None):
        """Initialize feature engineer."""
        self.config = config or FeatureConfig()
        self.scaler = StandardScaler() if self.config.normalize else None

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract all features from OHLCV data."""
        features = df.copy()

        # Technical indicators
        for indicator in self.config.technical_indicators:
            features = self._add_technical_indicator(features, indicator)

        # Price features
        for feature in self.config.price_features:
            features = self._add_price_feature(features, feature)

        # Rolling features
        for window in self.config.window_sizes:
            features = self._add_rolling_features(features, window)

        # Handle missing values
        features = self._handle_missing_values(features)

        # Normalize if configured
        if self.config.normalize and self.scaler:
            numeric_cols = features.select_dtypes(include=[np.number]).columns
            features[numeric_cols] = self.scaler.fit_transform(features[numeric_cols])

        return features

    def _add_technical_indicator(self, df: pd.DataFrame, indicator: str) -> pd.DataFrame:
        """Add technical indicator."""
        if indicator == "RSI":
            df["RSI"] = talib.RSI(df["close"], timeperiod=14)
        elif indicator == "MACD":
            macd, signal, hist = talib.MACD(df["close"])
            df["MACD"] = macd
            df["MACD_signal"] = signal
            df["MACD_hist"] = hist
        elif indicator == "BB":
            upper, middle, lower = talib.BBANDS(df["close"])
            df["BB_upper"] = upper
            df["BB_middle"] = middle
            df["BB_lower"] = lower
            df["BB_width"] = upper - lower
        elif indicator == "ATR":
            df["ATR"] = talib.ATR(df["high"], df["low"], df["close"])
        elif indicator == "ADX":
            df["ADX"] = talib.ADX(df["high"], df["low"], df["close"])
        elif indicator == "OBV":
            df["OBV"] = talib.OBV(df["close"], df["volume"])

        return df

    def _add_price_feature(self, df: pd.DataFrame, feature: str) -> pd.DataFrame:
        """Add price-based feature."""
        if feature == "returns":
            df["returns"] = df["close"].pct_change()
        elif feature == "log_returns":
            df["log_returns"] = np.log(df["close"] / df["close"].shift(1))
        elif feature == "volatility":
            df["volatility"] = df["returns"].rolling(20).std()
        elif feature == "volume_ratio":
            df["volume_ratio"] = df["volume"] / df["volume"].rolling(20).mean()

        return df

    def _add_rolling_features(self, df: pd.DataFrame, window: int) -> pd.DataFrame:
        """Add rolling window features."""
        df[f"SMA_{window}"] = df["close"].rolling(window).mean()
        df[f"STD_{window}"] = df["close"].rolling(window).std()
        df[f"MIN_{window}"] = df["close"].rolling(window).min()
        df[f"MAX_{window}"] = df["close"].rolling(window).max()
        df[f"VOLUME_MA_{window}"] = df["volume"].rolling(window).mean()

        return df

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values based on configuration."""
        if self.config.handle_missing == "forward_fill":
            return df.fillna(method="ffill")
        elif self.config.handle_missing == "backward_fill":
            return df.fillna(method="bfill")
        elif self.config.handle_missing == "interpolate":
            return df.interpolate()
        elif self.config.handle_missing == "drop":
            return df.dropna()
        return df


class FeaturePipeline:
    """Complete feature engineering pipeline."""

    def __init__(self):
        """Initialize pipeline."""
        self.engineer = FeatureEngineer()
        self.feature_importance = {}

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fit and transform data."""
        features = self.engineer.extract_features(df)
        self._calculate_feature_importance(features)
        return features

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform data using fitted parameters."""
        return self.engineer.extract_features(df)

    def _calculate_feature_importance(self, features: pd.DataFrame):
        """Calculate feature importance scores."""
        # Simple correlation-based importance
        if "returns" in features.columns:
            correlations = features.corr()["returns"].abs()
            self.feature_importance = correlations.sort_values(ascending=False).to_dict()

    def get_top_features(self, n: int = 10) -> list[str]:
        """Get top N important features."""
        sorted_features = sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)
        return [f[0] for f in sorted_features[:n]]
