from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.strategies.runner import RunResult, build_freqtrade_hyperopt_cmd, run_hyperopt


def test_build_freqtrade_hyperopt_cmd() -> None:
    """Test building a freqtrade hyperopt command."""
    config_path = Path("user_data/configs/config.bt.json")
    strategy = "MaCrossoverStrategy"
    spaces = ["buy", "sell", "roi", "stoploss"]
    epochs = 100

    cmd = build_freqtrade_hyperopt_cmd(
        config_path=config_path,
        strategy=strategy,
        spaces=spaces,
        epochs=epochs
    )

    import sys
    expected = [
        sys.executable,
        "-m",
        "freqtrade",
        "hyperopt",
        "--config",
        str(config_path),
        "--strategy",
        strategy,
        "--spaces",
        "buy sell roi stoploss",
        "--epochs",
        "100",
    ]

    assert cmd == expected


def test_build_freqtrade_hyperopt_cmd_with_optional_params() -> None:
    """Test building a freqtrade hyperopt command with optional parameters."""
    config_path = Path("user_data/configs/config.bt.json")
    strategy = "MaCrossoverStrategy"
    spaces = ["buy", "sell"]
    epochs = 50
    timerange = "20240101-20240701"
    timeframe = "5m"
    pairs_file = Path("user_data/pairs.txt")
    addl_args = ["--jobs", "4"]

    cmd = build_freqtrade_hyperopt_cmd(
        config_path=config_path,
        strategy=strategy,
        spaces=spaces,
        epochs=epochs,
        timerange=timerange,
        timeframe=timeframe,
        pairs_file=pairs_file,
        addl_args=addl_args
    )

    import sys
    expected = [
        sys.executable,
        "-m",
        "freqtrade",
        "hyperopt",
        "--config",
        str(config_path),
        "--strategy",
        strategy,
        "--spaces",
        "buy sell",
        "--epochs",
        "50",
        "--timerange",
        timerange,
        "--timeframe",
        timeframe,
        "--pairs-file",
        str(pairs_file),
        "--jobs",
        "4",
    ]

    assert cmd == expected

@patch('app.strategies.runner._run')
@patch('app.strategies.runner.RiskManager')
def test_run_hyperopt_success(mock_risk_manager: MagicMock, mock_run: MagicMock) -> None:
    """Test running hyperopt successfully."""
    # Setup mocks
    mock_rm = MagicMock()
    mock_rm.pre_run_check.return_value = (True, None)  # Allow run
    mock_rm.acquire_run_slot.return_value = (True, None, Path("/tmp/slot.lock"))  # Acquire slot
    mock_risk_manager.return_value = mock_rm

    mock_result = RunResult(0, "stdout output", "stderr output")
    mock_run.return_value = mock_result

    # Run the function
    result = run_hyperopt(
        config_path=Path("user_data/configs/config.bt.json"),
        strategy="MaCrossoverStrategy",
        spaces=["buy", "sell"],
        epochs=10
    )

    # Verify the result
    assert result.returncode == 0
    assert result.stdout == "stdout output"
    assert result.stderr == "stderr output"

    # Verify mocks were called correctly
    mock_risk_manager.assert_called_once()
    mock_rm.pre_run_check.assert_called_once()
    mock_rm.acquire_run_slot.assert_called_once()
    mock_run.assert_called_once()
    mock_rm.release_run_slot.assert_called_once()

@patch('app.strategies.runner._run')
@patch('app.strategies.runner.RiskManager')
def test_run_hyperopt_risk_blocked(mock_risk_manager: MagicMock, mock_run: MagicMock) -> None:
    """Test running hyperopt when blocked by risk manager."""
    # Setup mocks
    mock_rm = MagicMock()
    mock_rm.pre_run_check.return_value = (False, "test reason")  # Block run
    mock_risk_manager.return_value = mock_rm

    # Run the function
    result = run_hyperopt(
        config_path=Path("user_data/configs/config.bt.json"),
        strategy="MaCrossoverStrategy",
        spaces=["buy", "sell"],
        epochs=10
    )

    # Verify the result
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "Risk blocked: test reason"

    # Verify mocks were called correctly
    mock_risk_manager.assert_called_once()
    mock_rm.pre_run_check.assert_called_once()
    # Should not call acquire_run_slot or _run when blocked
    mock_rm.acquire_run_slot.assert_not_called()
    mock_run.assert_not_called()
    mock_rm.release_run_slot.assert_not_called()

@patch('app.strategies.runner._run')
@patch('app.strategies.runner.RiskManager')
def test_run_hyperopt_concurrency_blocked(mock_risk_manager: MagicMock, mock_run: MagicMock) -> None:
    """Test running hyperopt when blocked by concurrency limits."""
    # Setup mocks
    mock_rm = MagicMock()
    mock_rm.pre_run_check.return_value = (True, None)  # Allow run
    mock_rm.acquire_run_slot.return_value = (False, "test reason", None)  # Block slot
    mock_risk_manager.return_value = mock_rm

    # Run the function
    result = run_hyperopt(
        config_path=Path("user_data/configs/config.bt.json"),
        strategy="MaCrossoverStrategy",
        spaces=["buy", "sell"],
        epochs=10
    )

    # Verify the result
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "Risk concurrency blocked: test reason"

    # Verify mocks were called correctly
    mock_risk_manager.assert_called_once()
    mock_rm.pre_run_check.assert_called_once()
    mock_rm.acquire_run_slot.assert_called_once()
    # Should not call _run when blocked by concurrency
    mock_run.assert_not_called()
    mock_rm.release_run_slot.assert_not_called()
