from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from app.strategies.reporting import generate_results_markdown_from_db


def test_generate_results_markdown_includes_data_window_and_config_hash() -> None:
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = Path(tmp_db.name)

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Create minimal schema including optional columns used by reporting
    cur.execute(
        """
        CREATE TABLE experiments (
            id TEXT PRIMARY KEY,
            idea_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            hypothesis TEXT,
            timeframe TEXT,
            markets TEXT,
            period_start_utc TEXT,
            period_end_utc TEXT,
            seed INTEGER,
            config_hash TEXT,
            created_utc TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE runs (
            id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            kind TEXT,
            started_utc TEXT,
            finished_utc TEXT,
            status TEXT,
            docker_image TEXT,
            freqtrade_version TEXT,
            config_json TEXT,
            data_window TEXT,
            artifacts_path TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE metrics (
            run_id TEXT,
            key TEXT,
            value REAL,
            PRIMARY KEY (run_id, key)
        )
        """
    )

    # Insert an experiment with a config_hash
    exp_id = "exp_1"
    cur.execute(
        """
        INSERT INTO experiments (
            id, idea_id, strategy_id, hypothesis, timeframe, markets, period_start_utc, period_end_utc, seed, config_hash, created_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            exp_id,
            "idea_1",
            "StratA",
            "hyp",
            "5m",
            "",
            "2024-01-01T00:00:00Z",
            "2024-01-31T00:00:00Z",
            None,
            "abc123",
            "2024-02-01T00:00:00Z",
        ),
    )

    # Insert a run with a data_window
    run_id = "run_1"
    cur.execute(
        """
        INSERT INTO runs (
            id, experiment_id, kind, started_utc, finished_utc, status, docker_image, freqtrade_version, config_json, data_window, artifacts_path
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, NULL)
        """,
        (
            run_id,
            exp_id,
            "backtest",
            "2024-01-01T00:00:00Z",
            "2024-01-31T00:00:00Z",
            "completed",
            "2024-01-01T00:00:00+00:00..2024-01-31T00:00:00+00:00",
        ),
    )

    # Minimal metrics
    cur.execute("INSERT INTO metrics (run_id, key, value) VALUES (?, ?, ?)", (run_id, "profit_total", 1.0))

    con.commit()
    con.close()

    # Generate the report
    report = generate_results_markdown_from_db(db_path, limit=10)

    # Assertions for headers
    assert "Data Window" in report
    assert "Config Hash" in report

    # Assertions for values
    assert "2024-01-01T00:00:00+00:00..2024-01-31T00:00:00+00:00" in report
    assert "abc123" in report

    # Cleanup
    db_path.unlink()
