"""More comprehensive tests for the RiskManager, covering edge cases."""

from __future__ import annotations

import contextlib
import io
import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from app.strategies.logging_utils import JsonFormatter
from app.strategies.risk import RiskConfig, RiskManager


# --- Configuration Loading Tests ---


def test_risk_config_loading_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that RiskManager loads default config when no env vars are set."""
    # Ensure all relevant env vars are unset
    for key in [
        "RISK_MAX_CONCURRENT_BACKTESTS",
        "RISK_CONCURRENCY_TTL_SEC",
        "RISK_STATE_DIR",
        "RISK_CIRCUIT_BREAKER_FILE",
        "RISK_ALLOW_WHEN_CB",
        "RISK_MAX_BACKTEST_DRAWDOWN_PCT",
        "RISK_DB_PATH",
        "RISK_LIVE_MAX_CONCURRENT_TRADES",
        "RISK_LIVE_MAX_PER_MARKET_EXPOSURE_PCT",
    ]:
        monkeypatch.delenv(key, raising=False)

    rm = RiskManager()
    assert rm.cfg.max_concurrent_backtests is None
    assert rm.cfg.concurrency_ttl_sec == 900
    assert rm.cfg.allow_run_when_cb is False
    assert rm.cfg.max_backtest_drawdown_pct is None
    assert rm.cfg.live_max_concurrent_trades is None
    assert rm.cfg.live_max_per_market_exposure_pct is None


def test_risk_config_loading_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that RiskManager correctly loads config from environment variables."""
    db_path = tmp_path / "test.db"
    cb_file = tmp_path / "cb.json"

    monkeypatch.setenv("RISK_MAX_CONCURRENT_BACKTESTS", "5")
    monkeypatch.setenv("RISK_CONCURRENCY_TTL_SEC", "300")
    monkeypatch.setenv("RISK_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RISK_CIRCUIT_BREAKER_FILE", str(cb_file))
    monkeypatch.setenv("RISK_ALLOW_WHEN_CB", "true")
    monkeypatch.setenv("RISK_MAX_BACKTEST_DRAWDOWN_PCT", "15.5")
    monkeypatch.setenv("RISK_DB_PATH", str(db_path))
    monkeypatch.setenv("RISK_LIVE_MAX_CONCURRENT_TRADES", "10")
    monkeypatch.setenv("RISK_LIVE_MAX_PER_MARKET_EXPOSURE_PCT", "50")

    rm = RiskManager()
    assert rm.cfg.max_concurrent_backtests == 5
    assert rm.cfg.concurrency_ttl_sec == 300
    assert rm.cfg.state_dir == tmp_path
    assert rm.cfg.circuit_breaker_file == cb_file
    assert rm.cfg.allow_run_when_cb is True
    assert rm.cfg.max_backtest_drawdown_pct == 15.5
    assert rm.cfg.db_path == db_path
    assert rm.cfg.live_max_concurrent_trades == 10
    assert rm.cfg.live_max_per_market_exposure_pct == 50.0


def test_risk_config_loading_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that invalid numeric/bool env vars fall back to defaults."""
    monkeypatch.setenv("RISK_MAX_CONCURRENT_BACKTESTS", "not-a-number")
    monkeypatch.setenv("RISK_CONCURRENCY_TTL_SEC", "invalid")
    monkeypatch.setenv("RISK_ALLOW_WHEN_CB", "not-a-bool")

    rm = RiskManager()
    assert rm.cfg.max_concurrent_backtests is None
    assert rm.cfg.concurrency_ttl_sec == 900
    assert rm.cfg.allow_run_when_cb is False


# --- Circuit Breaker Edge Cases ---

def test_circuit_breaker_malformed_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that a malformed circuit breaker file is treated as active (fail-safe)."""
    cb_file = tmp_path / "circuit_breaker.json"
    cb_file.write_text("this is not json")
    monkeypatch.setenv("RISK_CIRCUIT_BREAKER_FILE", str(cb_file))
    monkeypatch.delenv("RISK_ALLOW_WHEN_CB", raising=False)

    rm = RiskManager()
    active, reason = rm._circuit_breaker_active(correlation_id=None)
    assert active is True
    assert reason == "circuit_breaker_parse_error"


def test_circuit_breaker_invalid_date(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that an invalid 'until_iso' date keeps the breaker active indefinitely."""
    cb_file = tmp_path / "circuit_breaker.json"
    payload = {"active": True, "reason": "test", "until_iso": "not-a-date"}
    cb_file.write_text(json.dumps(payload))
    monkeypatch.setenv("RISK_CIRCUIT_BREAKER_FILE", str(cb_file))

    rm = RiskManager()
    active, _ = rm._circuit_breaker_active(correlation_id=None)
    assert active is True


# --- Drawdown Guard Edge Cases ---

def test_drawdown_check_no_db_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test drawdown check returns None if DB file does not exist."""
    monkeypatch.setenv("RISK_DB_PATH", str(tmp_path / "non_existent.db"))
    rm = RiskManager()
    assert rm._recent_backtest_drawdown(correlation_id=None) is None


def test_drawdown_check_no_tables(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test drawdown check returns None if DB tables are missing."""
    db_path = tmp_path / "empty.db"
    db_path.touch()
    monkeypatch.setenv("RISK_DB_PATH", str(db_path))

    rm = RiskManager()
    assert rm._recent_backtest_drawdown(correlation_id=None) is None


# --- Incident Logging Tests ---

@pytest.mark.parametrize(
    "raw_severity, expected_severity",
    [
        ("CRITICAL", "critical"),
        (" Error ", "error"),
        ("warning", "warning"),
        ("info", "info"),
        ("unknown-level", "warning"),
        (None, "warning"),
        ("", "warning"),
    ],
)
def test_log_incident_severity_normalization(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raw_severity: str, expected_severity: str
) -> None:
    """Test that incident severity is correctly normalized."""
    db_path = tmp_path / "incidents.db"
    config = RiskConfig(db_path=db_path)
    rm = RiskManager(config)

    rm.log_incident(
        run_id="test_run",
        severity=raw_severity,
        description="A test incident",
        correlation_id="cid-123",
    )

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT severity FROM incidents")
    row = cur.fetchone()
    con.close()

    assert row is not None
    assert row[0] == expected_severity


# --- Concurrency Lock File Edge Cases ---

def test_create_lock_write_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that _create_lock handles write errors gracefully."""
    monkeypatch.setenv("RISK_STATE_DIR", str(tmp_path))
    rm = RiskManager()

    # Simulate a write error
    with patch("pathlib.Path.write_text", side_effect=PermissionError("Access denied")):
        lock_path = rm._create_lock(kind="backtest", correlation_id="cid-fail")

    # Should still return a path for potential cleanup, even if file creation failed
    assert lock_path is not None
    assert lock_path.name.startswith("backtest_")
    assert not lock_path.exists()  # File should not have been created


# --- New tests for increased coverage ---

def test_risk_config_loading_invalid_numeric_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that invalid numeric env vars for live guards fall back to None."""
    monkeypatch.setenv("RISK_LIVE_MAX_CONCURRENT_TRADES", "invalid")
    monkeypatch.setenv("RISK_LIVE_MAX_PER_MARKET_EXPOSURE_PCT", "invalid")
    monkeypatch.setenv("RISK_MAX_BACKTEST_DRAWDOWN_PCT", "invalid")

    rm = RiskManager()
    assert rm.cfg.live_max_concurrent_trades is None
    assert rm.cfg.live_max_per_market_exposure_pct is None
    assert rm.cfg.max_backtest_drawdown_pct is None


def test_check_risk_limits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test the check_risk_limits method."""
    cb_file = tmp_path / "cb.json"
    monkeypatch.setenv("RISK_CIRCUIT_BREAKER_FILE", str(cb_file))
    rm = RiskManager()

    # No circuit breaker file, should be OK
    assert rm.check_risk_limits() is True

    # Circuit breaker active
    cb_file.write_text(json.dumps({"active": True, "reason": "test"}))
    assert rm.check_risk_limits() is False

    # Circuit breaker inactive
    cb_file.write_text(json.dumps({"active": False}))
    assert rm.check_risk_limits() is True


def test_continue_pre_run_check_drawdown_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an exception in _recent_backtest_drawdown is handled."""
    config = RiskConfig(max_backtest_drawdown_pct=0.1)
    rm = RiskManager(config)
    with patch.object(rm, "_recent_backtest_drawdown", side_effect=Exception("DB error")):
        allowed, _ = rm._continue_pre_run_check("backtest", None, "cid-1")
        assert allowed is True  # Fails open


def test_live_guardrail_exposure_pct_over_100(tmp_path: Path) -> None:
    """Test live guardrail with exposure percentage > 1."""
    config = RiskConfig(live_max_per_market_exposure_pct=50)
    rm = RiskManager(config)
    context = {"market_exposure_pct": {"BTC/USDT": 75}}
    allowed, _ = rm._continue_pre_run_check("live", context, "cid-1")
    assert not allowed

    context = {"market_exposure_pct": {"BTC/USDT": "not-a-float"}}
    allowed, _ = rm._continue_pre_run_check("live", context, "cid-1")
    assert allowed is True


def test_acquire_run_slot_unbounded(tmp_path: Path) -> None:
    """Test that acquiring a slot works when no limit is set."""
    config = RiskConfig(max_concurrent_backtests=None, state_dir=tmp_path)
    rm = RiskManager(config)
    allowed, _, lock_path = rm.acquire_run_slot(kind="backtest", correlation_id="cid-1")
    assert allowed is True
    assert lock_path is not None
    rm.release_run_slot(lock_path, correlation_id="cid-1")


def test_release_run_slot_none_and_error(tmp_path: Path) -> None:
    """Test releasing a None slot and handling unlink errors."""
    config = RiskConfig(state_dir=tmp_path)
    rm = RiskManager(config)
    rm.release_run_slot(None, correlation_id="cid-1")  # Should not raise

    with patch("pathlib.Path.unlink", side_effect=OSError("test error")):
        # Create a dummy lock to attempt to release
        lock_path = rm._create_lock("backtest", "cid-error")
        rm.release_run_slot(lock_path, correlation_id="cid-error") # Should not raise


def test_count_active_locks_stat_fails(tmp_path: Path) -> None:
    """Test that _count_active_locks handles stat failures gracefully."""
    config = RiskConfig(state_dir=tmp_path)
    rm = RiskManager(config)
    running_dir = rm._running_dir()
    
    # Create a lock file that will cause stat to fail
    (running_dir / "backtest_stat_fail.lock").touch()

    # Patch stat to fail only for our target file
    original_stat = Path.stat
    def stat_wrapper(self, *args, **kwargs):
        if 'stat_fail' in self.name:
            raise FileNotFoundError("stat failed")
        return original_stat(self, *args, **kwargs)

    with patch("pathlib.Path.stat", new=stat_wrapper):
        # The lock that fails stat should be skipped, resulting in a count of 0
        assert rm._count_active_locks("backtest") == 0


def test_count_active_locks_generic_stat_error(tmp_path: Path) -> None:
    """Test _count_active_locks with a generic exception during stat."""
    config = RiskConfig(state_dir=tmp_path)
    rm = RiskManager(config)
    running_dir = rm._running_dir()
    lock_file = running_dir / "backtest_lock.lock"
    lock_file.touch()

    original_stat = Path.stat

    def stat_wrapper(self, *args, **kwargs):
        if self.name == lock_file.name:
            raise Exception("Unexpected stat error")
        return original_stat(self, *args, **kwargs)

    # Patch get_json_logger to intercept the logger creation
    with (
        patch("pathlib.Path.stat", new=stat_wrapper),
        patch("app.strategies.risk.get_json_logger") as mock_get_logger,
    ):
        mock_logger = mock_get_logger.return_value
        count = rm._count_active_locks("backtest")

        assert count == 0
        mock_logger.warning.assert_called_once()

        # The f-string in the code produces a single argument to the warning call.
        args, _ = mock_logger.warning.call_args
        assert len(args) == 1
        log_message = args[0]
        assert "Could not process lock file" in log_message
        assert lock_file.name in log_message
        assert "Unexpected stat error" in log_message


def test_count_active_locks_unlink_fails(tmp_path: Path) -> None:
    """Test that _count_active_locks handles unlink failures gracefully."""
    config = RiskConfig(state_dir=tmp_path, concurrency_ttl_sec=100)
    rm = RiskManager(config)
    running_dir = rm._running_dir()

    # Create a stale lock by manually setting its modification time in the past
    stale_lock = running_dir / "backtest_stale.lock"
    stale_lock.touch()
    stale_time = time.time() - 200  # 200 seconds in the past
    os.utime(stale_lock, (stale_time, stale_time))

    # Create a current lock
    current_lock = running_dir / "backtest_current.lock"
    current_lock.touch()

    # Patching in the module where it's used ensures the mock is applied correctly.
    with patch("app.strategies.risk.Path.unlink", side_effect=OSError("Permission denied")) as mock_unlink:
        # The stale lock is found and unlink is attempted (and fails).
        # It is not counted. Only the current lock is counted.
        assert rm._count_active_locks("backtest") == 1
        # Assert that unlink was called once. The instance it's called on is implicitly
        # the stale_lock object due to the code's logic, but it's not an argument.
        mock_unlink.assert_called_once()


def test_count_active_locks_no_dir(tmp_path: Path) -> None:
    """Test _count_active_locks when the running directory does not exist."""
    config = RiskConfig(state_dir=tmp_path)
    rm = RiskManager(config)
    # The running dir doesn't exist yet, so globbing should be skipped.
    assert rm._count_active_locks("backtest") == 0


def test_log_incident_db_error_and_coverage(tmp_path: Path) -> None:
    """Test incident logging during a DB error by patching get_json_logger."""
    db_path = tmp_path / "test.sqlite"
    config = RiskConfig(db_path=db_path)
    log_stream = io.StringIO()

    def logger_factory(name, *args, **kwargs):
        # Custom adapter to ensure 'extra' data is merged, not overwritten.
        class MergingLoggerAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                if 'extra' in kwargs:
                    kwargs['extra'] = {**self.extra, **kwargs['extra']}
                else:
                    kwargs['extra'] = self.extra
                return msg, kwargs

        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(JsonFormatter())
        logger = logging.getLogger(name)
        if logger.hasHandlers():
            logger.handlers.clear()
        logger.addHandler(handler)
        # The real get_json_logger passes static_fields to the adapter's extra.
        # Ensure we always have a dict for the adapter's extra.
        adapter_extra = kwargs.get('static_fields') or {}
        return MergingLoggerAdapter(logger, adapter_extra)

    with patch("app.strategies.risk.get_json_logger", new=logger_factory):
        # Instantiate RiskManager *inside* the patch to ensure all calls are intercepted
        rm = RiskManager(config)
        with patch("app.strategies.risk.sqlite_connect", side_effect=Exception("DB write failed")):
            rm.log_incident(run_id="run1", severity="info", description="coverage test")

    log_output = log_stream.getvalue().strip()
    log_lines = log_output.split('\n')
    assert len(log_lines) == 2

    # 1. Verify the initial incident log record (JSON)
    info_log = json.loads(log_lines[0])
    assert info_log["level"] == "INFO"
    assert info_log["message"] == "incident_logged"
    assert "incident" in info_log
    assert info_log["incident"]["description"] == "coverage test"

    # 2. Verify the subsequent error log record (JSON)
    error_log = json.loads(log_lines[1])
    assert error_log["level"] == "ERROR"
    assert error_log["message"] == "incident_store_error"
    assert "error" in error_log
    assert "DB write failed" in error_log["error"]


def test_circuit_breaker_no_config() -> None:
    """Test circuit breaker check when the file path is not configured."""
    config = RiskConfig(circuit_breaker_file=None)
    rm = RiskManager(config)
    active, reason = rm._circuit_breaker_active(correlation_id=None)
    assert not active
    assert reason is None


def test_circuit_breaker_no_file_and_inactive(tmp_path: Path) -> None:
    """Test circuit breaker when file is missing or inactive."""
    config = RiskConfig(circuit_breaker_file=tmp_path / "missing.json")
    rm = RiskManager(config)
    active, _ = rm._circuit_breaker_active(correlation_id=None)
    assert active is False

    cb_file = tmp_path / "cb.json"
    cb_file.write_text(json.dumps({"active": False}))
    config = RiskConfig(circuit_breaker_file=cb_file)
    rm = RiskManager(config)
    active, _ = rm._circuit_breaker_active(correlation_id=None)
    assert active is False


def test_circuit_breaker_naive_datetime(tmp_path: Path) -> None:
    """Test circuit breaker with a timezone-naive datetime string."""
    cb_file = tmp_path / "cb.json"
    # A naive datetime string that is in the past
    payload = {"active": True, "until_iso": "2020-01-01T00:00:00"}
    cb_file.write_text(json.dumps(payload))
    config = RiskConfig(circuit_breaker_file=cb_file)
    rm = RiskManager(config)
    active, _ = rm._circuit_breaker_active(correlation_id=None)
    assert active is False # Should be interpreted as expired


def test_recent_backtest_drawdown_edge_cases(tmp_path: Path) -> None:
    """Test edge cases for _recent_backtest_drawdown."""
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE runs (id TEXT, kind TEXT, started_utc TEXT)")
    con.execute("CREATE TABLE metrics (run_id TEXT, key TEXT, value TEXT)")
    con.execute("INSERT INTO runs VALUES ('r1', 'backtest', '2023-01-01T00:00:00Z')")
    con.execute("INSERT INTO metrics VALUES ('r1', 'max_drawdown_account', NULL)")
    con.commit()
    con.close()

    config = RiskConfig(db_path=db_path)
    rm = RiskManager(config)
    assert rm._recent_backtest_drawdown(correlation_id=None) is None

    con = sqlite3.connect(db_path)
    con.execute("UPDATE metrics SET value = 'not-a-float' WHERE run_id = 'r1'")
    con.commit()
    con.close()
    assert rm._recent_backtest_drawdown(correlation_id=None) is None

    con = sqlite3.connect(db_path)
    con.execute("DELETE FROM metrics")
    con.commit()
    con.close()
    assert rm._recent_backtest_drawdown(correlation_id=None) is None


def test_log_incident_db_error(tmp_path: Path) -> None:
    """Test that a DB error during incident logging is handled."""
    db_path = tmp_path / "incidents.db"
    config = RiskConfig(db_path=db_path)
    rm = RiskManager(config)

    with patch("app.strategies.persistence.sqlite.connect", side_effect=sqlite3.OperationalError("DB lock") ):
        rm.log_incident(run_id="run1", severity="error", description="test") # Should not raise

