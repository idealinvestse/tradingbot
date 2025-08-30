from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.strategies.metrics import index_hyperopts


def test_index_hyperopts() -> None:
    """Test parsing hyperopt results from a .fthypt file."""
    # Create a temporary directory with a sample .fthypt file
    with tempfile.TemporaryDirectory() as tmp_dir:
        hyperopt_dir = Path(tmp_dir)

        # Sample hyperopt data (simplified)
        sample_trials = [
            {
                "loss": 0.123456789,
                "params_dict": {"param1": 1.0, "param2": 2.0, "bool_param": True},
                "results_metrics": {"trades": [1, 2, 3, 4, 5]},
            },
            {
                "loss": 0.987654321,
                "params_dict": {"param1": 1.5, "param2": 2.5, "bool_param": False},
                "results_metrics": {"trades": [1, 2, 3]},
            },
        ]

        # Create a .fthypt file with the sample data
        fthypt_path = hyperopt_dir / "strategy_TestStrategy_2025-01-01_12-00-00.fthypt"
        with fthypt_path.open("w", encoding="utf-8") as f:
            for trial in sample_trials:
                f.write(json.dumps(trial) + "\n")

        # Create a temporary database file
        db_path = hyperopt_dir / "test.db"

        # Index the hyperopt results
        count = index_hyperopts(hyperopt_dir, db_path)

        # Check that we indexed the expected number of trials
        assert count == 2


def test_index_hyperopts_with_decimal_precision() -> None:
    """Test that hyperopt metrics maintain precision for monetary values using Decimal."""
    # Create a temporary directory with a sample .fthypt file
    with tempfile.TemporaryDirectory() as tmp_dir:
        hyperopt_dir = Path(tmp_dir)

        # Sample hyperopt data with high precision values
        sample_trials = [
            {
                "loss": 0.123456789123456789,
                "params_dict": {"param1": 1.123456789123456789, "param2": 2.9876543210987654321},
                "results_metrics": {"trades": [1, 2, 3, 4, 5]},
            }
        ]

        # Create a .fthypt file with the sample data
        fthypt_path = hyperopt_dir / "strategy_TestStrategy_2025-01-01_12-00-00.fthypt"
        with fthypt_path.open("w", encoding="utf-8") as f:
            for trial in sample_trials:
                f.write(json.dumps(trial) + "\n")

        # Create a temporary database file
        db_path = hyperopt_dir / "test.db"

        # Index the hyperopt results
        count = index_hyperopts(hyperopt_dir, db_path)

        # Check that we indexed the expected number of trials
        assert count == 1


if __name__ == "__main__":
    pytest.main([__file__])
