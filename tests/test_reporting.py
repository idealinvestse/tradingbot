from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.strategies.reporting import generate_results_markdown_from_db


def test_generate_results_markdown_from_db_with_decimal_precision() -> None:
    """Test that generate_results_markdown_from_db maintains precision for monetary values using Decimal."""
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = Path(tmp_db.name)

    # Create the database schema
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Create tables
    cur.execute(
        """
        CREATE TABLE runs (
            id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            kind TEXT,
            started_utc TEXT,
            finished_utc TEXT,
            status TEXT
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

    # Insert test data
    run_id = "test_run_1"
    cur.execute(
        """
        INSERT INTO runs (id, experiment_id, kind, started_utc, finished_utc, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (run_id, "exp_1", "backtest", "2025-01-01T12:00:00Z", "2025-01-01T13:00:00Z", "completed"),
    )

    # Insert metrics with high precision values
    metrics = {
        "profit_total": 0.123456789123456789,
        "profit_total_abs": 123.456789123456789,
        "max_drawdown_abs": 5.123456789123456789,
        "sharpe": 1.23456789,
        "sortino": 2.34567890,
        "winrate": 0.65432109,
        "loss": 0.987654321,
        "trades": 100.0,
    }

    for key, value in metrics.items():
        cur.execute(
            """
            INSERT INTO metrics (run_id, key, value)
            VALUES (?, ?, ?)
        """,
            (run_id, key, value),
        )

    con.commit()
    con.close()

    # Generate the report
    report = generate_results_markdown_from_db(db_path, limit=10)

    # Check that the report contains the expected values
    assert "Resultat – senaste körningar" in report
    assert run_id in report

    # Check that monetary values are displayed with 8 decimal places
    assert "0.12345679" in report  # profit_total should be rounded to 8 decimal places
    assert "123.45678912" in report  # profit_total_abs should be rounded to 8 decimal places
    assert "5.12345679" in report  # max_drawdown_abs should be rounded to 8 decimal places

    # Clean up
    db_path.unlink()


def test_generate_results_markdown_from_db_empty() -> None:
    """Test that generate_results_markdown_from_db handles empty database correctly."""
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = Path(tmp_db.name)

    # Create the database schema
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Create tables
    cur.execute(
        """
        CREATE TABLE runs (
            id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            kind TEXT,
            started_utc TEXT,
            finished_utc TEXT,
            status TEXT
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

    con.commit()
    con.close()

    # Generate the report
    report = generate_results_markdown_from_db(db_path, limit=10)

    # Check that the report contains the expected message
    assert "Resultat – senaste körningar" in report
    assert "Inga körningar hittades." in report

    # Clean up
    db_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__])
