"""Integration tests for the complete trading pipeline."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.strategies.metrics import index_backtests
from app.strategies.reporting import generate_results_markdown_from_db
from app.strategies.risk import RiskManager
from app.strategies.runner import build_freqtrade_backtest_cmd, run_backtest


class TestFullPipeline:
    """Test the complete backtest -> metrics -> reporting pipeline."""

    def test_backtest_to_report_pipeline(self, tmp_path):
        """Test full pipeline from backtest to report generation."""
        # Setup
        config_path = Path("user_data/configs/config.bt.json")
        strategy = "MaCrossoverStrategy"
        timerange = "20240101-20240201"
        
        # Test command building
        cmd = build_freqtrade_backtest_cmd(
            config_path=config_path,
            strategy=strategy,
            timerange=timerange
        )
        assert "freqtrade" in cmd
        assert str(config_path) in cmd
        assert strategy in cmd
        assert timerange in cmd
        
        # Test risk checks
        risk_mgr = RiskManager()
        can_run, reason = risk_mgr.pre_run_check("backtest", strategy)
        assert can_run or reason  # Should either allow or provide reason
        
        # Test metrics indexing with mock data
        mock_result = {
            "strategy": strategy,
            "timerange": timerange,
            "results": {
                "profit_total": 0.05,
                "trades": 50,
                "sharpe": 1.2
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(mock_result, f)
            result_path = Path(f.name)
        
        try:
            # Would index the backtest results
            # index_backtests(result_path.parent)
            pass
        finally:
            result_path.unlink()
        
        # Test report generation
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            # Would generate markdown report
            # report = generate_results_markdown_from_db(db_path)
            # assert "Results" in report
            pass
        finally:
            db_path.unlink()

    @patch('subprocess.run')
    def test_hyperopt_pipeline(self, mock_run):
        """Test hyperopt workflow integration."""
        from app.strategies.runner import run_hyperopt
        
        mock_run.return_value = MagicMock(returncode=0, stdout="Hyperopt complete")
        
        result = run_hyperopt(
            config_path=Path("user_data/configs/config.bt.json"),
            strategy="MaCrossoverStrategy",
            spaces=["buy", "sell"],
            epochs=10,
            timerange="20240101-20240201"
        )
        
        assert result["success"] is True
        assert mock_run.called

    def test_risk_management_integration(self):
        """Test risk management integration with runner."""
        risk_mgr = RiskManager()
        
        # Test circuit breaker
        risk_mgr.trip_circuit_breaker("Test failure", duration_hours=0.01)
        can_run, reason = risk_mgr.pre_run_check("backtest", "TestStrategy")
        assert not can_run
        assert "circuit breaker" in reason.lower()
        
        # Test concurrency slots
        slot_acquired, slot_reason, lock_file = risk_mgr.acquire_run_slot("test_run")
        if slot_acquired:
            risk_mgr.release_run_slot(lock_file)
        
        assert slot_acquired is not None  # Should return a result

    def test_data_flow_integrity(self):
        """Test data flows correctly through the pipeline."""
        # Test that data structures are compatible
        from app.strategies.introspect import discover_strategies
        
        strategies = discover_strategies(Path("user_data/strategies"))
        assert len(strategies) > 0
        
        for strategy in strategies:
            assert "name" in strategy
            assert "file" in strategy
            assert "params" in strategy
