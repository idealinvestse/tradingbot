"""More comprehensive tests for the RiskManager, covering edge cases."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

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

