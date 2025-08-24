from __future__ import annotations

import pytest

from app.strategies.risk import RiskManager


def test_live_concurrent_trades_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RISK_LIVE_MAX_CONCURRENT_TRADES", "3")

    rm = RiskManager()

    allowed, reason = rm.pre_run_check(
        kind="live",
        strategy="S",
        timeframe=None,
        context={"open_trades_count": 4},
        correlation_id=None,
    )
    assert not allowed
    assert reason and "live_concurrent_trades_exceeded" in reason

    allowed2, reason2 = rm.pre_run_check(
        kind="live",
        strategy="S",
        timeframe=None,
        context={"open_trades_count": 2},
        correlation_id=None,
    )
    assert allowed2
    assert reason2 is None


def test_live_per_market_exposure_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RISK_LIVE_MAX_PER_MARKET_EXPOSURE_PCT", "0.25")

    rm = RiskManager()

    allowed, reason = rm.pre_run_check(
        kind="live",
        strategy="S",
        timeframe=None,
        context={"market_exposure_pct": {"BTC/USDT": 0.3, "ETH/USDT": 0.1}},
        correlation_id=None,
    )
    assert not allowed
    assert reason and "per_market_exposure_exceeded" in reason

    allowed2, reason2 = rm.pre_run_check(
        kind="live",
        strategy="S",
        timeframe=None,
        context={"market_exposure_pct": {"BTC/USDT": 0.1, "ETH/USDT": 0.2}},
        correlation_id=None,
    )
    assert allowed2
    assert reason2 is None
