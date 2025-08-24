from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app.strategies.risk import RiskManager


def test_concurrency_single_slot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RISK_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RISK_MAX_CONCURRENT_BACKTESTS", "1")

    rm = RiskManager()

    ok1, _, lock1 = rm.acquire_run_slot(kind="backtest", correlation_id=None)
    assert ok1 and lock1 is not None and lock1.exists()

    ok2, reason2, lock2 = rm.acquire_run_slot(kind="backtest", correlation_id=None)
    assert not ok2 and lock2 is None
    assert reason2 and "too_many_active_backtests" in reason2

    rm.release_run_slot(lock1, correlation_id=None)

    ok3, _, lock3 = rm.acquire_run_slot(kind="backtest", correlation_id=None)
    assert ok3 and lock3 is not None
    rm.release_run_slot(lock3, correlation_id=None)


def test_concurrency_ttl_cleanup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RISK_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RISK_MAX_CONCURRENT_BACKTESTS", "1")
    monkeypatch.setenv("RISK_CONCURRENCY_TTL_SEC", "1")

    rm = RiskManager()

    running_dir = tmp_path / "running"
    running_dir.mkdir(parents=True, exist_ok=True)
    stale = running_dir / "backtest_0_12345_stale.lock"
    stale.write_text("{}", encoding="utf-8")
    # Set mtime to old
    old_time = time.time() - 10
    os.utime(stale, (old_time, old_time))

    ok, _, lock = rm.acquire_run_slot(kind="backtest", correlation_id=None)
    assert ok and lock is not None
    rm.release_run_slot(lock, correlation_id=None)
