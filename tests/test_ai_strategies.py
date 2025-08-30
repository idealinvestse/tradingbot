"""
Unit tests for AI strategy modules.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest

# Import from actual modules
from pydantic import ValidationError

from app.strategies.ai_executor import (
    AIStrategyConfig,
    AIStrategyExecutor,
    ExecutionResult,
    StrategySignal,
)
from app.strategies.ai_registry import AIStrategyRegistry, AIStrategyType
from app.strategies.ai_storage import AIStrategyStorage
from app.strategies.metrics_collector import MetricsCollector
from app.strategies.risk import RiskManager


@pytest.fixture
def sample_market_data():
    """Create sample market data for testing."""
    dates = pd.date_range(end=datetime.utcnow(), periods=100, freq="1h")
    data = pd.DataFrame(
        {
            "open": [50000 + i * 10 for i in range(100)],
            "high": [50100 + i * 10 for i in range(100)],
            "low": [49900 + i * 10 for i in range(100)],
            "close": [50050 + i * 10 for i in range(100)],
            "volume": [100 + i for i in range(100)],
        },
        index=dates,
    )
    return data


@pytest.fixture
def sample_context():
    """Create sample context for testing."""
    return {
        "symbol": "BTC/USDT",
        "sentiment_score": 0.7,
        "order_book_imbalance": 0.15,
        "spread_percentage": 0.2,
        "volume_spike": 1.5,
        "portfolio_weights": {"BTC": 0.4, "ETH": 0.3, "SOL": 0.3},
        "grid_levels": [49000, 50000, 51000],
        "dca_threshold": -0.05,
        "narrative_topics": ["DeFi growth", "ETF approval"],
    }


@pytest.fixture
def mock_registry():
    """Mock AIStrategyRegistry."""
    return MagicMock(spec=AIStrategyRegistry)


@pytest.fixture
def mock_risk_manager():
    """Mock RiskManager."""
    mock = MagicMock(spec=RiskManager)
    mock.check_risk_limits.return_value = True
    return mock


@pytest.fixture
def mock_metrics_collector():
    """Mock MetricsCollector."""
    return MetricsCollector()


@pytest.fixture
def mock_storage():
    """Mock AIStrategyStorage."""
    mock = MagicMock(spec=AIStrategyStorage)
    mock.save_signal = MagicMock()
    return mock


@pytest.fixture
def ai_executor(mock_registry, mock_risk_manager, mock_metrics_collector, mock_storage):
    """Create AI strategy executor instance with mocks."""
    return AIStrategyExecutor(
        registry=mock_registry,
        risk_manager=mock_risk_manager,
        metrics_collector=mock_metrics_collector,
        storage=mock_storage,
    )


@pytest.fixture
def get_default_config():
    """Returns a function to create a default AIStrategyConfig for testing."""

    def _get_config(**kwargs):
        defaults = {
            "name": "Test Strategy",
            "strategy_type": AIStrategyType.SENTIMENT_ANALYSIS,
            "description": "Test description",
            "mechanics": "Test mechanics",
            "why_effective": "Test effectiveness",
            "example": "Test example",
            "performance_metrics": "Test metrics",
            "2025_insights": "Test insights",
            "enabled": True,
        }
        defaults.update(kwargs)
        return AIStrategyConfig(**defaults)

    return _get_config


@pytest.fixture
def ai_registry():
    """Create a fresh AI strategy registry instance for each test."""
    return AIStrategyRegistry()


class TestAIStrategyRegistry:
    """Test AI strategy registry."""

    def test_register_strategy(self, ai_registry, get_default_config):
        """Test registering a strategy."""
        config = get_default_config(
            name="Test Strategy", strategy_type=AIStrategyType.SENTIMENT_ANALYSIS
        )

        ai_registry.register_strategy(config)
        key = f"{config.strategy_type.value.lower()}_{config.name.lower().replace(' ', '_')}"
        assert key in ai_registry.strategies

    def test_get_strategy(self, ai_registry, get_default_config):
        """Test getting a strategy."""
        config = get_default_config(
            name="Test Strategy", strategy_type=AIStrategyType.SENTIMENT_ANALYSIS
        )

        ai_registry.register_strategy(config)
        key = f"{config.strategy_type.value.lower()}_{config.name.lower().replace(' ', '_')}"
        retrieved = ai_registry.get_strategy(key)
        assert retrieved is not None
        assert retrieved.name == "Test Strategy"

    def test_list_strategies(self, ai_registry, get_default_config):
        """Test listing strategies."""
        # Clear default strategies for a clean test
        ai_registry.strategies = {}

        config1 = get_default_config(
            name="Strategy 1", strategy_type=AIStrategyType.SENTIMENT_ANALYSIS, enabled=True
        )
        config2 = get_default_config(
            name="Strategy 2", strategy_type=AIStrategyType.PREDICTIVE_MODELING, enabled=False
        )

        ai_registry.register_strategy(config1)
        ai_registry.register_strategy(config2)

        strategies = ai_registry.strategies
        assert len(strategies) == 2

        enabled = ai_registry.get_enabled_strategies()
        assert len(enabled) == 1
        assert all(s.enabled for s in enabled)


class TestAIStrategyExecutor:
    """Test AI strategy executor."""

    @pytest.mark.asyncio
    async def test_execute_sentiment_analysis(
        self, ai_executor, sample_market_data, sample_context, get_default_config
    ):
        """Test sentiment analysis strategy execution."""
        config = get_default_config(
            name="Test Sentiment",
            strategy_type=AIStrategyType.SENTIMENT_ANALYSIS,
            min_confidence=0.5,
        )

        result = await ai_executor.execute_strategy(config, sample_market_data, sample_context)

        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert result.signal is not None
        assert result.strategy_type == AIStrategyType.SENTIMENT_ANALYSIS
        assert result.signal.action == "buy"
        assert result.signal.confidence >= 0.5
        ai_executor.risk_manager.check_risk_limits.assert_called_once()
        ai_executor.storage.save_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_predictive_modeling(
        self, ai_executor, sample_market_data, sample_context, get_default_config
    ):
        """Test predictive modeling strategy execution."""
        config = get_default_config(
            name="Test Predictive",
            strategy_type=AIStrategyType.PREDICTIVE_MODELING,
            lookback_period=50,
            min_confidence=0.6,
        )

        result = await ai_executor.execute_strategy(config, sample_market_data, sample_context)

        assert result.success is True
        assert result.signal is not None
        assert result.signal.entry_price > 0
        assert result.signal.stop_loss < result.signal.entry_price

    @pytest.mark.asyncio
    async def test_risk_manager_blocks_execution(
        self, ai_executor, sample_market_data, sample_context, get_default_config
    ):
        """Test that risk manager can block execution."""
        ai_executor.risk_manager.check_risk_limits.return_value = False
        config = get_default_config(
            name="Test Sentiment",
            strategy_type=AIStrategyType.SENTIMENT_ANALYSIS,
            min_confidence=0.5,
        )

        result = await ai_executor.execute_strategy(config, sample_market_data, sample_context)

        assert result.success is False
        assert result.signal is None
        assert "Risk limits exceeded" in result.error
        ai_executor.storage.save_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_all_strategies(
        self, ai_executor, sample_market_data, sample_context, get_default_config
    ):
        """Test executing multiple strategies concurrently."""
        configs = [
            get_default_config(
                name="S1", strategy_type=AIStrategyType.SENTIMENT_ANALYSIS, min_confidence=0.5
            ),
            get_default_config(
                name="S2", strategy_type=AIStrategyType.MOMENTUM_TRADING, min_confidence=0.5
            ),
        ]
        ai_executor.registry.get_enabled_strategies.return_value = configs

        results = await ai_executor.execute_all_strategies(sample_market_data, sample_context)

        assert len(results) == 2
        assert sum(1 for r in results if r.success) > 0

    @pytest.mark.asyncio
    async def test_empty_market_data(self, ai_executor, sample_context, get_default_config):
        """Test strategy execution with empty market data."""
        config = get_default_config(
            name="Test Strategy",
            strategy_type=AIStrategyType.PREDICTIVE_MODELING,
            min_confidence=0.6,
        )

        empty_data = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = await ai_executor.execute_strategy(config, empty_data, sample_context)

        assert result.success is True
        assert result.signal is not None
        assert result.signal.entry_price > 0

    def test_validate_signal(self, ai_executor, get_default_config):
        """Test signal validation logic in the executor."""
        config = get_default_config(
            name="Test",
            strategy_type=AIStrategyType.SENTIMENT_ANALYSIS,
            min_confidence=0.8,
            max_risk_per_trade=0.05,
        )

        # Valid signal
        signal = StrategySignal(
            strategy_name="Test",
            strategy_type=AIStrategyType.SENTIMENT_ANALYSIS,
            symbol="BTC/USDT",
            action="buy",
            confidence=0.85,
            suggested_size=0.02,
            entry_price=50000.0,
            rationale="test",
        )
        validated = ai_executor._validate_signal(signal, config)
        assert validated is not None

        # Confidence too low
        low_confidence_signal = signal.model_copy(update={"confidence": 0.7})
        assert ai_executor._validate_signal(low_confidence_signal, config) is None

        # Adjust position size
        large_size_signal = signal.model_copy(update={"suggested_size": 0.1})
        validated_resized = ai_executor._validate_signal(large_size_signal, config)
        assert validated_resized.suggested_size == config.max_risk_per_trade


class TestAIStrategyStorage:
    """Test AI strategy storage."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database."""
        db_path = tmp_path / "test_ai.db"
        storage = AIStrategyStorage(db_path=str(db_path))
        return storage

    def test_save_signal(self, temp_db):
        """Test saving a signal."""
        signal = StrategySignal(
            strategy_name="Test Strategy",
            strategy_type=AIStrategyType.SENTIMENT_ANALYSIS,
            symbol="BTC/USDT",
            action="buy",
            confidence=0.75,
            suggested_size=0.1,
            entry_price=50000.0,
            rationale="Positive sentiment surge",
        )

        temp_db.save_signal(
            strategy_name="Test Strategy",
            signal_data=signal.model_dump(),
            timestamp=datetime.utcnow(),
        )

        signals = temp_db.get_ai_signals(strategy_name="Test Strategy")
        assert len(signals) == 1
        assert signals[0]["strategy_name"] == "Test Strategy"
        assert signals[0]["confidence"] == 0.75

    def test_get_signals(self, temp_db):
        """Test retrieving signals."""
        signal1 = StrategySignal(
            strategy_name="S1",
            strategy_type=AIStrategyType.SENTIMENT_ANALYSIS,
            symbol="BTC/USDT",
            action="buy",
            confidence=0.8,
            rationale="test1",
            suggested_size=0.1,
        )
        signal2 = StrategySignal(
            strategy_name="S2",
            strategy_type=AIStrategyType.PREDICTIVE_MODELING,
            symbol="ETH/USDT",
            action="sell",
            confidence=0.9,
            rationale="test2",
            suggested_size=0.05,
        )

        temp_db.save_signal("S1", signal1.model_dump(), datetime.utcnow())
        temp_db.save_signal("S2", signal2.model_dump(), datetime.utcnow() - timedelta(minutes=10))

        signals = temp_db.get_ai_signals()
        assert len(signals) == 2

        s1_signals = temp_db.get_ai_signals(strategy_name="S1")
        assert len(s1_signals) == 1
        assert s1_signals[0]["strategy_name"] == "S1"

    def test_update_metrics(self, temp_db):
        """Test updating metrics."""
        metrics = {"strategy_type": "Test Type", "total_signals": 10, "win_rate": 0.7}
        temp_db.update_metrics("Test Strategy", metrics)

        retrieved_metrics = temp_db.get_ai_metrics(strategy_name="Test Strategy")
        assert retrieved_metrics is not None
        assert retrieved_metrics["total_signals"] == 10
        assert retrieved_metrics["win_rate"] == 0.7

    def test_database_initialization(self, temp_db):
        """Test database tables are created correctly."""
        # Attempting to get data from a fresh DB should return empty lists, not raise an error
        assert temp_db.get_ai_signals() == []
        assert temp_db.get_ai_metrics() == []
        assert temp_db.get_ai_trades() == []


class TestStrategySignalModel:
    """Test StrategySignal model."""

    def test_signal_validation(self):
        """Test signal model validation."""
        # Valid signal
        signal = StrategySignal(
            strategy_name="Test",
            strategy_type=AIStrategyType.SENTIMENT_ANALYSIS,
            symbol="BTC/USDT",
            action="buy",
            confidence=0.8,
            suggested_size=0.1,
            rationale="test",
        )
        assert signal.confidence == 0.8

        # Invalid confidence (should raise pydantic.ValidationError)
        with pytest.raises(ValidationError):
            StrategySignal(
                strategy_name="Test",
                strategy_type=AIStrategyType.SENTIMENT_ANALYSIS,
                symbol="BTC/USDT",
                action="buy",
                confidence=1.5,  # Invalid: > 1.0
                suggested_size=0.1,
                rationale="test",
            )

    def test_signal_json_serialization(self):
        """Test signal JSON serialization."""
        signal = StrategySignal(
            strategy_name="Test Strategy",
            strategy_type=AIStrategyType.GRID_TRADING,
            symbol="SOL/USDT",
            action="sell",
            confidence=0.65,
            suggested_size=0.05,
            rationale="Grid level reached",
        )

        # Convert to dict
        signal_dict = signal.model_dump()
        assert signal_dict["strategy_name"] == "Test Strategy"
        assert signal_dict["confidence"] == 0.65

        # Convert to JSON
        signal_json = signal.model_dump_json()
        parsed = json.loads(signal_json)
        assert parsed["symbol"] == "SOL/USDT"


class TestIntegration:
    """Integration tests for AI strategy system."""

    @pytest.mark.asyncio
    async def test_full_execution_flow(
        self, tmp_path, sample_market_data, sample_context, get_default_config
    ):
        """Test complete execution flow from registry to storage."""
        # Setup
        db_path = tmp_path / "integration_test.db"
        storage = AIStrategyStorage(db_path=str(db_path))
        registry = AIStrategyRegistry()  # Empty registry
        registry.strategies = {}  # Clear default strategies for a clean test
        risk_manager = RiskManager()
        metrics_collector = MetricsCollector()
        executor = AIStrategyExecutor(registry, risk_manager, metrics_collector, storage)

        # Register strategy
        config = get_default_config(
            name="Integration Test Strategy",
            strategy_type=AIStrategyType.MOMENTUM_TRADING,
            min_confidence=0.6,
        )
        registry.register_strategy(config)

        # Execute strategy
        result = await executor.execute_strategy(config, sample_market_data, sample_context)

        assert result.success is True
        assert result.signal is not None

        # Verify storage
        saved_signals = storage.get_ai_signals(strategy_name=config.name)
        assert len(saved_signals) == 1
        assert saved_signals[0]["action"] == result.signal.action
