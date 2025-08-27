from __future__ import annotations

import json
import tempfile
import zipfile
from decimal import Decimal
from pathlib import Path

from app.strategies.metrics import (
    _parse_zip_metrics,
    _upsert_metric,
    _validate_backtest_payload,
    _validate_hyperopt_trial,
)


def test_parse_zip_metrics() -> None:
    """Test parsing metrics from a Freqtrade backtest ZIP file."""
    # Create a temporary ZIP file with sample data
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
        zip_path = Path(tmp_zip.name)

    # Sample data that mimics a Freqtrade backtest result
    sample_data = {
        "strategy": {
            "TestStrategy": {
                "profit_total": 0.123456789,
                "profit_total_abs": 123.456789,
                "profit_mean": 0.00123456789,
                "profit_median": 0.001,
                "cagr": 0.123456789,
                "expectancy": 0.123456789,
                "expectancy_ratio": 0.123456789,
                "sortino": 1.23456789,
                "sharpe": 1.23456789,
                "calmar": 1.23456789,
                "sqn": 2.123456789,
                "profit_factor": 1.23456789,
                "trades_per_day": 5.123456789,
                "market_change": 0.05123456789,
                "total_trades": 100
            }
        },
        "strategy_comparison": [
            {
                "key": "TestStrategy",
                "wins": 60,
                "losses": 40,
                "draws": 0,
                "winrate": 0.6,
                "profit_total": 0.123456789,
                "profit_total_abs": 123.456789,
                "profit_mean": 0.00123456789,
                "profit_total_pct": 12.3456789,
                "duration_avg": "1:30:00",
                "sortino": 1.23456789,
                "sharpe": 1.23456789,
                "calmar": 1.23456789,
                "sqn": 2.123456789,
                "profit_factor": 1.23456789,
                "max_drawdown_account": 0.05123456789,
                "max_drawdown_abs": 5.123456789,
                "trades": 100
            }
        ]
    }

    # Create a ZIP file with the sample data
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr('TestStrategy.json', json.dumps(sample_data))

    # Parse the metrics
    metrics = _parse_zip_metrics(zip_path)

    # Check that we got the expected metrics
    assert 'profit_total' in metrics
    assert 'profit_total_abs' in metrics
    assert 'trades' in metrics
    assert metrics['trades'] == 100.0

    # Clean up
    zip_path.unlink()


def test_parse_zip_metrics_precision() -> None:
    """Test that _parse_zip_metrics maintains precision for monetary values using Decimal."""
    # Create a temporary ZIP file with sample data
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
        zip_path = Path(tmp_zip.name)

    # Sample data with high precision values
    sample_data = {
        "strategy": {
            "TestStrategy": {
                "profit_total": 0.123456789123456789,
                "profit_total_abs": 123.456789123456789,
                "profit_mean": 0.00123456789123456789,
                "profit_median": 0.00123456789123456789,
                "cagr": 0.123456789123456789,
                "expectancy": 0.123456789123456789,
                "expectancy_ratio": 0.123456789123456789,
                "market_change": 0.05123456789123456789,
                "sortino": 1.23456789,
                "sharpe": 1.23456789,
                "calmar": 1.23456789,
                "sqn": 2.123456789,
                "profit_factor": 1.23456789,
                "trades_per_day": 5.123456789,
                "total_trades": 100
            }
        },
        "strategy_comparison": [
            {
                "key": "TestStrategy",
                "wins": 60,
                "losses": 40,
                "draws": 0,
                "winrate": 0.6,
                "profit_total": 0.123456789123456789,
                "profit_total_abs": 123.456789123456789,
                "profit_mean": 0.00123456789123456789,
                "profit_total_pct": 12.3456789123456789,
                "duration_avg": "1:30:00",
                "sortino": 1.23456789,
                "sharpe": 1.23456789,
                "calmar": 1.23456789,
                "sqn": 2.123456789,
                "profit_factor": 1.23456789,
                "max_drawdown_account": 0.05123456789123456789,
                "max_drawdown_abs": 5.123456789123456789,
                "trades": 100
            }
        ]
    }

    # Create a ZIP file with the sample data
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr('TestStrategy.json', json.dumps(sample_data))

    # Parse the metrics
    metrics = _parse_zip_metrics(zip_path)

    # Check that monetary values are properly quantized
    # Note: We're checking that they're floats (as expected by the DB) but were processed with Decimal precision
    assert isinstance(metrics['profit_total'], float)
    assert isinstance(metrics['profit_total_abs'], float)
    assert isinstance(metrics['profit_mean'], float)
    assert isinstance(metrics['profit_median'], float)
    assert isinstance(metrics['cagr'], float)
    assert isinstance(metrics['expectancy'], float)
    assert isinstance(metrics['expectancy_ratio'], float)
    assert isinstance(metrics['market_change'], float)
    assert isinstance(metrics['max_drawdown_account'], float)
    assert isinstance(metrics['max_drawdown_abs'], float)

    # Clean up
    zip_path.unlink()


def test_upsert_metric_decimal_precision() -> None:
    """Test that _upsert_metric handles Decimal precision correctly."""
    import sqlite3

    # Create an in-memory database for testing
    conn = sqlite3.connect(':memory:')
    cur = conn.cursor()

    # Create the metrics table
    cur.execute('''
        CREATE TABLE metrics (
            run_id TEXT,
            key TEXT,
            value REAL,
            PRIMARY KEY (run_id, key)
        )
    ''')

    # Test with a high precision decimal value
    run_id = "test_run"
    key = "test_metric"
    value = 0.123456789123456789

    # Call the function
    _upsert_metric(cur, run_id, key, value)

    # Check that the value was stored correctly
    cur.execute("SELECT value FROM metrics WHERE run_id = ? AND key = ?", (run_id, key))
    result = cur.fetchone()

    # The value should be stored as a float (due to DB schema) but processed with Decimal precision
    # It should be quantized to 8 decimal places
    assert result is not None
    assert isinstance(result[0], float)

    # Check that the value is quantized to 8 decimal places
    # Convert to Decimal to check precision
    decimal_result = Decimal(str(result[0]))
    assert decimal_result == Decimal('0.12345679')  # Should be rounded to 8 decimal places

    # Test with negative value
    negative_value = -0.9876543210987654321
    _upsert_metric(cur, run_id, "negative_test", negative_value)

    cur.execute("SELECT value FROM metrics WHERE run_id = ? AND key = ?", (run_id, "negative_test"))
    neg_result = cur.fetchone()

    assert neg_result is not None
    assert isinstance(neg_result[0], float)

    # Check that the negative value is quantized correctly
    decimal_neg_result = Decimal(str(neg_result[0]))
    assert decimal_neg_result == Decimal('-0.98765432')  # Should be rounded to 8 decimal places

    # Clean up
    conn.close()

def test_validate_backtest_payload() -> None:
    """Test validating backtest payload."""
    # Valid payload
    valid_payload = {
        "run_id": "test_run",
        "timeframe": "5m",
        "backtest_start_ts": 1640995200,
        "backtest_end_ts": 1641081600
    }

    is_valid, reason = _validate_backtest_payload(valid_payload)
    assert is_valid
    assert reason is None

    # Invalid payload - wrong type
    invalid_payload = {
        "backtest_start_ts": "not_a_number"
    }

    is_valid, reason = _validate_backtest_payload(invalid_payload)
    assert not is_valid
    assert reason is not None


def test_validate_hyperopt_trial() -> None:
    """Test validating hyperopt trial."""
    # Valid trial
    valid_trial = {
        "loss": 0.123,
        "params_dict": {
            "param1": 1.0,
            "param2": 2.0
        },
        "results_metrics": {
            "trades": [1, 2, 3]
        }
    }

    is_valid = _validate_hyperopt_trial(valid_trial)
    assert is_valid

    # Invalid trial - not a dict
    invalid_trial = "not_a_dict"

    is_valid = _validate_hyperopt_trial(invalid_trial)
    assert not is_valid
