from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.strategies.risk import RiskManager


def _init_db(db_path: Path) -> None:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            experiment_id TEXT,
            kind TEXT,
            started_utc TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
            run_id TEXT,
            key TEXT,
            value REAL,
            PRIMARY KEY (run_id, key)
        )
        """
    )
    con.commit()
    con.close()


def test_drawdown_blocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = tmp_path / "registry.sqlite"
    _init_db(db)
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO runs(id, experiment_id, kind, started_utc) VALUES (?,?,?,?)",
        ("r1", "e1", "backtest", "2025-08-17T00:00:00Z"),
    )
    cur.execute(
        "INSERT INTO metrics(run_id, key, value) VALUES (?,?,?)",
        ("r1", "max_drawdown_account", 25.0),
    )
    con.commit()
    con.close()

    monkeypatch.setenv("RISK_DB_PATH", str(db))
    monkeypatch.setenv("RISK_MAX_BACKTEST_DRAWDOWN_PCT", "0.2")

    rm = RiskManager()
    allowed, reason = rm.pre_run_check(
        kind="backtest", strategy="S", timeframe=None, context=None, correlation_id=None
    )
    assert not allowed
    assert reason and "recent_drawdown_exceeded" in reason


def test_drawdown_allows_when_within_threshold(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = tmp_path / "registry.sqlite"
    _init_db(db)
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO runs(id, experiment_id, kind, started_utc) VALUES (?,?,?,?)",
        ("r1", "e1", "backtest", "2025-08-17T00:00:00Z"),
    )
    cur.execute(
        "INSERT INTO metrics(run_id, key, value) VALUES (?,?,?)",
        ("r1", "max_drawdown_account", 0.1),
    )
    con.commit()
    con.close()

    monkeypatch.setenv("RISK_DB_PATH", str(db))
    monkeypatch.setenv("RISK_MAX_BACKTEST_DRAWDOWN_PCT", "0.2")

    rm = RiskManager()
    allowed, reason = rm.pre_run_check(
        kind="backtest", strategy="S", timeframe=None, context=None, correlation_id=None
    )
    assert allowed
    assert reason is None
