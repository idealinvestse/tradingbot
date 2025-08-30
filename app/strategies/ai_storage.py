"""SQLite storage extensions for AI strategies."""

import json
import sqlite3
from datetime import datetime
from typing import Any, Optional

from app.strategies.utils import get_json_logger

logger = get_json_logger("ai_storage")


class AIStrategyStorage:
    """Storage handler for AI strategy data."""

    def __init__(self, db_path: str = "user_data/backtest_results/index.db"):
        """Initialize storage."""
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create AI signals table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    strategy_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    suggested_size REAL,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    rationale TEXT,
                    metadata TEXT,
                    correlation_id TEXT,
                    timestamp TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create AI metrics table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    strategy_type TEXT NOT NULL,
                    total_signals INTEGER DEFAULT 0,
                    successful_signals INTEGER DEFAULT 0,
                    failed_signals INTEGER DEFAULT 0,
                    avg_confidence REAL DEFAULT 0.0,
                    total_return REAL DEFAULT 0.0,
                    avg_return REAL DEFAULT 0.0,
                    sharpe_ratio REAL DEFAULT 0.0,
                    max_drawdown REAL DEFAULT 0.0,
                    win_rate REAL DEFAULT 0.0,
                    profit_factor REAL DEFAULT 0.0,
                    model_accuracy REAL DEFAULT 0.0,
                    specific_metrics TEXT,
                    last_signal_time TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(strategy_name)
                )
            """
            )

            # Create AI trades table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    strategy_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL,
                    exit_price REAL,
                    quantity REAL,
                    pnl REAL,
                    pnl_percent REAL,
                    fees REAL,
                    success BOOLEAN,
                    trade_data TEXT,
                    correlation_id TEXT,
                    opened_at TEXT,
                    closed_at TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.commit()
            logger.info("AI strategy tables initialized")

    def save_signal(self, strategy_name: str, signal_data: dict, timestamp: datetime) -> None:
        """Save an AI strategy signal."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO ai_signals (
                    strategy_name, strategy_type, symbol, action, confidence,
                    suggested_size, entry_price, stop_loss, take_profit,
                    rationale, metadata, correlation_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    strategy_name,
                    signal_data.get("strategy_type", ""),
                    signal_data.get("symbol", ""),
                    signal_data.get("action", ""),
                    signal_data.get("confidence", 0.0),
                    signal_data.get("suggested_size"),
                    signal_data.get("entry_price"),
                    signal_data.get("stop_loss"),
                    signal_data.get("take_profit"),
                    signal_data.get("rationale", ""),
                    json.dumps(signal_data.get("metadata", {})),
                    signal_data.get("correlation_id", ""),
                    timestamp.isoformat(),
                ),
            )
            conn.commit()
            logger.info(f"Saved AI signal for {strategy_name}")

    def save_trade_result(self, strategy_name: str, trade_data: dict, correlation_id: str) -> None:
        """Save an AI strategy trade result."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO ai_trades (
                    strategy_name, strategy_type, symbol, side, entry_price,
                    exit_price, quantity, pnl, pnl_percent, fees,
                    success, trade_data, correlation_id, opened_at, closed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    strategy_name,
                    trade_data.get("strategy_type", ""),
                    trade_data.get("symbol", ""),
                    trade_data.get("side", ""),
                    trade_data.get("entry_price"),
                    trade_data.get("exit_price"),
                    trade_data.get("quantity"),
                    trade_data.get("pnl", 0.0),
                    trade_data.get("pnl_percent", 0.0),
                    trade_data.get("fees", 0.0),
                    trade_data.get("success", False),
                    json.dumps(trade_data),
                    correlation_id,
                    trade_data.get("opened_at", ""),
                    trade_data.get("closed_at", ""),
                ),
            )
            conn.commit()
            logger.info(f"Saved AI trade result for {strategy_name}")

    def update_metrics(self, strategy_name: str, metrics: dict) -> None:
        """Update or insert AI strategy metrics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO ai_metrics (
                    strategy_name, strategy_type, total_signals, successful_signals,
                    failed_signals, avg_confidence, total_return, avg_return,
                    sharpe_ratio, max_drawdown, win_rate, profit_factor,
                    model_accuracy, specific_metrics, last_signal_time, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    strategy_name,
                    metrics.get("strategy_type", ""),
                    metrics.get("total_signals", 0),
                    metrics.get("successful_signals", 0),
                    metrics.get("failed_signals", 0),
                    metrics.get("avg_confidence", 0.0),
                    metrics.get("total_return", 0.0),
                    metrics.get("avg_return", 0.0),
                    metrics.get("sharpe_ratio", 0.0),
                    metrics.get("max_drawdown", 0.0),
                    metrics.get("win_rate", 0.0),
                    metrics.get("profit_factor", 0.0),
                    metrics.get("model_accuracy", 0.0),
                    json.dumps(metrics.get("specific_metrics", {})),
                    metrics.get("last_signal_time", ""),
                ),
            )
            conn.commit()
            logger.info(f"Updated AI metrics for {strategy_name}")

    def get_ai_signals(self, strategy_name: Optional[str] = None, limit: int = 100) -> list[dict[str, Any]]:
        """Get AI strategy signals."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if strategy_name:
                cursor.execute(
                    "SELECT * FROM ai_signals WHERE strategy_name = ? ORDER BY timestamp DESC LIMIT ?",
                    (strategy_name, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM ai_signals ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )

            return [dict(row) for row in cursor.fetchall()]

    def get_ai_trades(self, strategy_name: Optional[str] = None, limit: int = 100) -> list[dict[str, Any]]:
        """Get AI strategy trade results."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if strategy_name:
                cursor.execute(
                    "SELECT * FROM ai_trades WHERE strategy_name = ? ORDER BY closed_at DESC LIMIT ?",
                    (strategy_name, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM ai_trades ORDER BY closed_at DESC LIMIT ?",
                    (limit,),
                )

            return [dict(row) for row in cursor.fetchall()]

    def get_ai_metrics(self, strategy_name: Optional[str] = None) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Get AI strategy metrics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if strategy_name:
                cursor.execute(
                    "SELECT * FROM ai_metrics WHERE strategy_name = ?",
                    (strategy_name,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
            else:
                cursor.execute("SELECT * FROM ai_metrics ORDER BY strategy_name")
                return [dict(row) for row in cursor.fetchall()]

    def get_strategy_performance_summary(self) -> list[dict[str, Any]]:
        """Get performance summary for all strategies."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    strategy_name,
                    strategy_type,
                    total_signals,
                    win_rate,
                    total_return,
                    sharpe_ratio,
                    max_drawdown,
                    last_signal_time
                FROM ai_metrics
                ORDER BY total_return DESC
            """
            )

            return [dict(row) for row in cursor.fetchall()]
