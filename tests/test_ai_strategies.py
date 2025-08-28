"""
Unit tests for AI strategy modules.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

# Import from actual modules
from app.strategies.ai_executor import AIStrategyExecutor, AIStrategyConfig, StrategySignal
from app.strategies.ai_metrics import AIMetricsTracker
from app.strategies.ai_registry import AIStrategyRegistry
from app.strategies.ai_storage import AIStrategyStorage


@pytest.fixture
def sample_market_data():
    """Create sample market data for testing."""
    dates = pd.date_range(end=datetime.utcnow(), periods=100, freq="1h")
    data = pd.DataFrame({
        "open": [50000 + i * 10 for i in range(100)],
        "high": [50100 + i * 10 for i in range(100)],
        "low": [49900 + i * 10 for i in range(100)],
        "close": [50050 + i * 10 for i in range(100)],
        "volume": [100 + i for i in range(100)]
    }, index=dates)
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
        "narrative_topics": ["DeFi growth", "ETF approval"]
    }


@pytest.fixture
def ai_executor():
    """Create AI strategy executor instance."""
    return AIStrategyExecutor()


@pytest.fixture
def ai_registry():
    """Create AI strategy registry instance."""
    return AIStrategyRegistry()


class TestAIStrategyRegistry:
    """Test AI strategy registry."""
    
    def test_register_strategy(self, ai_registry):
        """Test registering a strategy."""
        config = AIStrategyConfig(
            name="Test Strategy",
            strategy_type="sentiment_analysis",
            enabled=True,
            min_confidence=0.6
        )
        
        ai_registry.register_strategy(config)
        assert "sentiment_analysis_test_strategy" in ai_registry.strategies
        
    def test_get_strategy(self, ai_registry):
        """Test getting a strategy."""
        config = AIStrategyConfig(
            name="Test Strategy",
            strategy_type="sentiment_analysis",
            enabled=True
        )
        
        ai_registry.register_strategy(config)
        retrieved = ai_registry.get_strategy("sentiment_analysis_test_strategy")
        assert retrieved is not None
        assert retrieved.name == "Test Strategy"
        
    def test_list_strategies(self, ai_registry):
        """Test listing strategies."""
        config1 = AIStrategyConfig(
            name="Strategy 1",
            strategy_type="sentiment_analysis",
            enabled=True
        )
        config2 = AIStrategyConfig(
            name="Strategy 2",
            strategy_type="predictive_modeling",
            enabled=False
        )
        
        ai_registry.register_strategy(config1)
        ai_registry.register_strategy(config2)
        
        strategies = ai_registry.list_strategies()
        assert len(strategies) >= 2
        
        enabled = ai_registry.list_strategies(enabled_only=True)
        assert all(s.enabled for s in enabled)


class TestAIStrategyExecutor:
    """Test AI strategy executor."""
    
    @pytest.mark.asyncio
    async def test_execute_sentiment_analysis(self, ai_executor, sample_market_data, sample_context):
        """Test sentiment analysis strategy execution."""
        config = AIStrategyConfig(
            name="Test Sentiment",
            strategy_type="sentiment_analysis",
            enabled=True,
            min_confidence=0.5
        )
        
        signal = await ai_executor.execute_strategy(
            config, sample_market_data, sample_context
        )
        
        assert signal is not None
        assert signal.strategy_type == "sentiment_analysis"
        assert signal.action in ["buy", "sell", "hold"]
        assert signal.confidence >= 0.5
        assert signal.entry_price > 0
        
    @pytest.mark.asyncio
    async def test_execute_predictive_modeling(self, ai_executor, sample_market_data, sample_context):
        """Test predictive modeling strategy execution."""
        config = AIStrategyConfig(
            name="Test Predictive",
            strategy_type="predictive_modeling",
            enabled=True,
            lookback_period=50
        )
        
        signal = await ai_executor.execute_strategy(
            config, sample_market_data, sample_context
        )
        
        assert signal is not None
        assert signal.strategy_type == "predictive_modeling"
        assert signal.entry_price > 0
        assert signal.stop_loss < signal.entry_price
        assert signal.take_profit > signal.entry_price
        
    @pytest.mark.asyncio
    async def test_execute_arbitrage(self, ai_executor, sample_market_data, sample_context):
        """Test arbitrage strategy execution."""
        config = AIStrategyConfig(
            name="Test Arbitrage",
            strategy_type="arbitrage",
            enabled=True
        )
        
        signal = await ai_executor.execute_strategy(
            config, sample_market_data, sample_context
        )
        
        assert signal is not None
        assert signal.strategy_type == "arbitrage"
        assert signal.confidence > 0.5
        
    @pytest.mark.asyncio
    async def test_execute_multiple_concurrent(self, ai_executor, sample_market_data, sample_context):
        """Test executing multiple strategies concurrently."""
        configs = [
            AIStrategyConfig(
                name=f"Strategy {i}",
                strategy_type=st,
                enabled=True
            )
            for i, st in enumerate([
                "sentiment_analysis",
                "momentum_trading",
                "dca_timing"
            ])
        ]
        
        results = await ai_executor.execute_multiple(
            configs, sample_market_data, sample_context
        )
        
        assert len(results["successful"]) > 0
        assert all(isinstance(s, StrategySignal) for s in results["successful"])
        
    @pytest.mark.asyncio
    async def test_empty_market_data(self, ai_executor, sample_context):
        """Test strategy execution with empty market data."""
        config = AIStrategyConfig(
            name="Test Strategy",
            strategy_type="momentum_trading",
            enabled=True
        )
        
        empty_data = pd.DataFrame()
        signal = await ai_executor.execute_strategy(
            config, empty_data, sample_context
        )
        
        # Should still generate signal with default values
        assert signal is not None
        assert signal.entry_price > 0
        
    def test_validate_signal(self, ai_executor):
        """Test signal validation."""
        valid_signal = StrategySignal(
            strategy_name="Test",
            strategy_type="sentiment_analysis",
            symbol="BTC/USDT",
            action="buy",
            confidence=0.8,
            suggested_size=0.1,
            entry_price=50000.0,
            stop_loss=48000.0,
            take_profit=52000.0
        )
        
        assert ai_executor._validate_signal(valid_signal) is True
        
        invalid_signal = StrategySignal(
            strategy_name="Test",
            strategy_type="sentiment_analysis",
            symbol="BTC/USDT",
            action="buy",
            confidence=1.5,  # Invalid confidence > 1
            suggested_size=0.1,
            entry_price=50000.0
        )
        
        assert ai_executor._validate_signal(invalid_signal) is False


class TestAIStrategyStorage:
    """Test AI strategy storage."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database."""
        db_path = tmp_path / "test_ai.db"
        return AIStrategyStorage(str(db_path))
        
    def test_save_signal(self, temp_db):
        """Test saving a signal."""
        signal = StrategySignal(
            strategy_name="Test Strategy",
            strategy_type="sentiment_analysis",
            symbol="BTC/USDT",
            action="buy",
            confidence=0.75,
            suggested_size=0.1,
            entry_price=50000.0,
            stop_loss=48000.0,
            take_profit=52000.0,
            rationale="Test signal"
        )
        
        signal_id = temp_db.save_signal(signal)
        assert signal_id is not None
        assert signal_id > 0
        
    def test_get_signals(self, temp_db):
        """Test getting signals."""
        # Save multiple signals
        for i in range(3):
            signal = StrategySignal(
                strategy_name=f"Strategy {i}",
                strategy_type="momentum_trading",
                symbol="ETH/USDT",
                action="buy" if i % 2 == 0 else "sell",
                confidence=0.6 + i * 0.1,
                suggested_size=0.1
            )
            temp_db.save_signal(signal)
            
        # Get all signals
        signals = temp_db.get_signals()
        assert len(signals) == 3
        
        # Get by strategy
        momentum_signals = temp_db.get_signals(strategy_name="Strategy 1")
        assert len(momentum_signals) == 1
        assert momentum_signals[0]["strategy_name"] == "Strategy 1"
        
    def test_update_metrics(self, temp_db):
        """Test updating metrics."""
        metrics = {
            "total_signals": 10,
            "successful_signals": 7,
            "win_rate": 0.7,
            "total_return": 0.15,
            "sharpe_ratio": 1.2
        }
        
        temp_db.update_metrics("Test Strategy", metrics)
        
        retrieved = temp_db.get_metrics("Test Strategy")
        assert retrieved is not None
        assert retrieved["total_signals"] == 10
        assert retrieved["win_rate"] == 0.7
        
    def test_database_initialization(self, temp_db):
        """Test database tables are created correctly."""
        # Check signals table exists
        temp_db.conn.execute("SELECT * FROM ai_signals LIMIT 1")
        
        # Check metrics table exists  
        temp_db.conn.execute("SELECT * FROM ai_metrics LIMIT 1")
        
        # Check configs table exists
        temp_db.conn.execute("SELECT * FROM ai_configs LIMIT 1")


class TestStrategySignalModel:
    """Test StrategySignal model."""
    
    def test_signal_validation(self):
        """Test signal model validation."""
        # Valid signal
        signal = StrategySignal(
            strategy_name="Test",
            strategy_type="sentiment_analysis",
            symbol="BTC/USDT",
            action="buy",
            confidence=0.8,
            suggested_size=0.1
        )
        assert signal.confidence == 0.8
        
        # Invalid confidence (should be clamped or raise error)
        with pytest.raises(Exception):
            StrategySignal(
                strategy_name="Test",
                strategy_type="sentiment_analysis",
                symbol="BTC/USDT",
                action="invalid_action",  # Invalid action
                confidence=0.8,
                suggested_size=0.1
            )
            
    def test_signal_json_serialization(self):
        """Test signal JSON serialization."""
        signal = StrategySignal(
            strategy_name="Test Strategy",
            strategy_type="grid_trading",
            symbol="SOL/USDT",
            action="sell",
            confidence=0.65,
            suggested_size=0.05,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=105.0,
            rationale="Grid level reached"
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
    async def test_full_execution_flow(self, tmp_path, sample_market_data, sample_context):
        """Test complete execution flow from registry to storage."""
        # Setup
        db_path = tmp_path / "integration_test.db"
        storage = AIStrategyStorage(str(db_path))
        registry = AIStrategyRegistry()
        executor = AIStrategyExecutor()
        
        # Register strategy
        config = AIStrategyConfig(
            name="Integration Test Strategy",
            strategy_type="momentum_trading",
            enabled=True,
            min_confidence=0.6
        )
        registry.register_strategy(config)
        
        # Execute strategy
        signal = await executor.execute_strategy(
            config, sample_market_data, sample_context
        )
        
        assert signal is not None
        
        # Save signal
        signal_id = storage.save_signal(signal)
        assert signal_id > 0
        
        # Update metrics
        metrics = {
            "total_signals": 1,
            "successful_signals": 1,
            "win_rate": 1.0
        }
        storage.update_metrics(config.name, metrics)
        
        # Verify storage
        saved_signals = storage.get_signals(strategy_name=config.name)
        assert len(saved_signals) == 1
        assert saved_signals[0]["action"] == signal.action
        
        saved_metrics = storage.get_metrics(config.name)
        assert saved_metrics["total_signals"] == 1
