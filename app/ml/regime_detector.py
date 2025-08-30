"""Market regime detection using ML models."""

from enum import Enum

import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from app.strategies.utils import get_json_logger

logger = get_json_logger("regime_detector")


class MarketRegime(str, Enum):
    """Market regime types."""

    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"


class RegimeConfig(BaseModel):
    """Regime detection configuration."""

    lookback_periods: int = 60
    volatility_threshold: float = 0.02
    trend_threshold: float = 0.01
    features: list[str] = ["returns", "volatility", "volume", "momentum"]
    model_type: str = "clustering"  # clustering, classification, rule_based


class RegimeDetector:
    """Detect market regimes using various methods."""

    def __init__(self, config: RegimeConfig = None):
        """Initialize regime detector."""
        self.config = config or RegimeConfig()
        self.scaler = StandardScaler()
        self.model = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize detection model based on config."""
        if self.config.model_type == "clustering":
            self.model = KMeans(n_clusters=4, random_state=42)
        elif self.config.model_type == "classification":
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)

    def detect_regime(self, df: pd.DataFrame) -> MarketRegime:
        """Detect current market regime."""
        if self.config.model_type == "rule_based":
            return self._rule_based_detection(df)
        else:
            return self._ml_detection(df)

    def _rule_based_detection(self, df: pd.DataFrame) -> MarketRegime:
        """Rule-based regime detection."""
        recent_data = df.tail(self.config.lookback_periods)

        # Calculate metrics
        returns = recent_data["close"].pct_change()
        avg_return = returns.mean()
        volatility = returns.std()

        # Trend calculation
        start_price = recent_data["close"].iloc[0]
        end_price = recent_data["close"].iloc[-1]
        trend = (end_price - start_price) / start_price

        # Determine regime
        if volatility > self.config.volatility_threshold:
            return MarketRegime.VOLATILE
        elif trend > self.config.trend_threshold:
            return MarketRegime.BULL
        elif trend < -self.config.trend_threshold:
            return MarketRegime.BEAR
        else:
            return MarketRegime.SIDEWAYS

    def _ml_detection(self, df: pd.DataFrame) -> MarketRegime:
        """ML-based regime detection."""
        features = self._extract_features(df)

        if features is None or len(features) == 0:
            return MarketRegime.SIDEWAYS

        # Scale features
        features_scaled = self.scaler.fit_transform(features.reshape(1, -1))

        # Predict regime
        if self.config.model_type == "clustering":
            cluster = self.model.predict(features_scaled)[0]
            return self._map_cluster_to_regime(cluster, features)
        else:
            # For classification, would need trained model
            return MarketRegime.SIDEWAYS

    def _extract_features(self, df: pd.DataFrame) -> np.ndarray | None:
        """Extract features for regime detection."""
        try:
            recent_data = df.tail(self.config.lookback_periods)
            features = []

            if "returns" in self.config.features:
                returns = recent_data["close"].pct_change()
                features.extend([returns.mean(), returns.std()])

            if "volatility" in self.config.features:
                volatility = recent_data["close"].rolling(20).std().mean()
                features.append(volatility)

            if "volume" in self.config.features:
                volume_ratio = (
                    recent_data["volume"].mean() / recent_data["volume"].rolling(50).mean().mean()
                )
                features.append(volume_ratio)

            if "momentum" in self.config.features:
                momentum = (
                    recent_data["close"].iloc[-1] - recent_data["close"].iloc[0]
                ) / recent_data["close"].iloc[0]
                features.append(momentum)

            return np.array(features)
        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return None

    def _map_cluster_to_regime(self, cluster: int, features: np.ndarray) -> MarketRegime:
        """Map cluster to market regime."""
        # Simple mapping based on feature values
        returns_mean = features[0] if len(features) > 0 else 0
        volatility = features[1] if len(features) > 1 else 0

        if volatility > self.config.volatility_threshold:
            return MarketRegime.VOLATILE
        elif returns_mean > self.config.trend_threshold:
            return MarketRegime.BULL
        elif returns_mean < -self.config.trend_threshold:
            return MarketRegime.BEAR
        else:
            return MarketRegime.SIDEWAYS

    def train_classifier(self, historical_data: pd.DataFrame, labels: list[MarketRegime]):
        """Train classification model on historical data."""
        if self.config.model_type != "classification":
            logger.warning("Training only supported for classification model")
            return

        features_list = []
        for i in range(self.config.lookback_periods, len(historical_data)):
            window_data = historical_data.iloc[i - self.config.lookback_periods : i]
            features = self._extract_features(window_data)
            if features is not None:
                features_list.append(features)

        if features_list:
            X = np.array(features_list)
            X_scaled = self.scaler.fit_transform(X)
            y = [label.value for label in labels[: len(X)]]

            self.model.fit(X_scaled, y)
            logger.info("Regime classifier trained")


class RegimeAdaptiveStrategy:
    """Adapt strategy based on detected market regime."""

    def __init__(self):
        """Initialize regime adaptive strategy."""
        self.detector = RegimeDetector()
        self.regime_params = {
            MarketRegime.BULL: {
                "risk_multiplier": 1.5,
                "stop_loss": 0.02,
                "take_profit": 0.05,
                "position_size": 1.2,
            },
            MarketRegime.BEAR: {
                "risk_multiplier": 0.5,
                "stop_loss": 0.01,
                "take_profit": 0.02,
                "position_size": 0.5,
            },
            MarketRegime.SIDEWAYS: {
                "risk_multiplier": 1.0,
                "stop_loss": 0.015,
                "take_profit": 0.03,
                "position_size": 0.8,
            },
            MarketRegime.VOLATILE: {
                "risk_multiplier": 0.3,
                "stop_loss": 0.005,
                "take_profit": 0.015,
                "position_size": 0.3,
            },
        }

    def get_regime_params(self, df: pd.DataFrame) -> dict:
        """Get parameters based on current regime."""
        regime = self.detector.detect_regime(df)
        logger.info(f"Detected regime: {regime}")
        return self.regime_params[regime]

    def adjust_signal(self, signal: str, regime: MarketRegime) -> str:
        """Adjust trading signal based on regime."""
        if regime == MarketRegime.VOLATILE:
            # Reduce trading in volatile markets
            return "hold" if signal != "strong_buy" else "buy"
        elif regime == MarketRegime.BEAR:
            # Be more conservative in bear markets
            return "hold" if signal == "buy" else signal
        else:
            return signal
