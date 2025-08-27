from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.strategies.risk import RiskManager


def _make_cb_file(tmp_path: Path, *, active: bool, until_iso: str | None = None, reason: str = "test") -> Path:
    path = tmp_path / "circuit_breaker.json"
    payload = {"active": active, "reason": reason}
    if until_iso is not None:
        payload["until_iso"] = until_iso
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_circuit_breaker_blocks_when_active(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
    cb_file = _make_cb_file(tmp_path, active=True, until_iso=future)
    monkeypatch.setenv("RISK_CIRCUIT_BREAKER_FILE", str(cb_file))
    monkeypatch.setenv("RISK_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("RISK_ALLOW_WHEN_CB", raising=False)

    rm = RiskManager()
    allowed, reason = rm.pre_run_check(
        kind="backtest", strategy="X", timeframe=None, context=None, correlation_id=None
    )
    assert not allowed
    assert reason and "circuit_breaker_active" in reason


def test_circuit_breaker_expires(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    past = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
    cb_file = _make_cb_file(tmp_path, active=True, until_iso=past)
    monkeypatch.setenv("RISK_CIRCUIT_BREAKER_FILE", str(cb_file))
    monkeypatch.setenv("RISK_STATE_DIR", str(tmp_path))

    rm = RiskManager()
    allowed, reason = rm.pre_run_check(
        kind="backtest", strategy="X", timeframe=None, context=None, correlation_id=None
    )
    assert allowed
    assert reason is None


def test_circuit_breaker_allow_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
    cb_file = _make_cb_file(tmp_path, active=True, until_iso=future)
    monkeypatch.setenv("RISK_CIRCUIT_BREAKER_FILE", str(cb_file))
    monkeypatch.setenv("RISK_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RISK_ALLOW_WHEN_CB", "1")

    rm = RiskManager()
    allowed, reason = rm.pre_run_check(
        kind="backtest", strategy="X", timeframe=None, context=None, correlation_id=None
    )
    assert allowed
    assert reason is None
