from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.strategies.risk import RiskConfig, RiskManager


def test_log_incident() -> None:
    """Test that incidents are logged to the database correctly."""
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = Path(tmp_db.name)

    # Create the database schema
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Create incidents table
    cur.execute('''
        CREATE TABLE incidents (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            severity TEXT,
            description TEXT,
            log_excerpt_path TEXT,
            created_utc TEXT
        )
    ''')

    con.commit()
    con.close()

    # Create a RiskManager with the database path
    config = RiskConfig(db_path=db_path)
    risk_manager = RiskManager(config)

    # Log an incident
    risk_manager.log_incident(
        run_id="test_run_1",
        severity="warning",
        description="Test incident",
        log_excerpt_path="/path/to/log",
        correlation_id="test_correlation_id"
    )

    # Check that the incident was logged to the database
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT id, run_id, severity, description, log_excerpt_path FROM incidents")
    rows = cur.fetchall()
    con.close()

    # Verify that exactly one incident was logged
    assert len(rows) == 1

    # Verify the incident details
    incident_id, run_id, severity, description, log_excerpt_path = rows[0]
    assert run_id == "test_run_1"
    assert severity == "warning"
    assert description == "Test incident"
    assert log_excerpt_path == "/path/to/log"
    assert incident_id.startswith("incident_")

    # Clean up
    db_path.unlink()


def test_log_incident_without_db() -> None:
    """Test that incidents are handled correctly when no database is configured."""
    # Create a RiskManager without a database path
    config = RiskConfig(db_path=None)
    risk_manager = RiskManager(config)

    # Log an incident - this should not raise an exception
    risk_manager.log_incident(
        run_id="test_run_1",
        severity="warning",
        description="Test incident",
        log_excerpt_path="/path/to/log",
        correlation_id="test_correlation_id"
    )

    # No assertions needed - the test passes if no exception is raised

if __name__ == "__main__":
    pytest.main([__file__])
