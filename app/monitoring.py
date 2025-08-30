"""Performance monitoring and metrics collection system."""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from app.strategies.utils import get_json_logger

logger = get_json_logger("monitoring")


class PerformanceMetric(BaseModel):
    """Single performance metric."""

    name: str
    value: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tags: dict[str, str] = Field(default_factory=dict)
    unit: str | None = None


class MetricsCollector:
    """Collect and aggregate performance metrics."""

    def __init__(self, storage_path: Path | None = None):
        """Initialize metrics collector."""
        self.storage_path = storage_path or Path("user_data/metrics")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.metrics: list[PerformanceMetric] = []
        self.timers: dict[str, float] = {}
        self.counters: dict[str, int] = defaultdict(int)
        self.gauges: dict[str, float] = {}

    def start_timer(self, name: str) -> None:
        """Start a timer for measuring duration."""
        self.timers[name] = time.time()

    def stop_timer(self, name: str, tags: dict[str, str] | None = None) -> float:
        """Stop a timer and record the duration."""
        if name not in self.timers:
            logger.warning(f"Timer {name} not started")
            return 0.0

        duration = time.time() - self.timers[name]
        del self.timers[name]

        metric = PerformanceMetric(
            name=f"timer.{name}", value=duration, tags=tags or {}, unit="seconds"
        )
        self.metrics.append(metric)
        self._persist_metric(metric)

        return duration

    def increment_counter(
        self, name: str, value: int = 1, tags: dict[str, str] | None = None
    ) -> None:
        """Increment a counter."""
        self.counters[name] += value

        metric = PerformanceMetric(
            name=f"counter.{name}", value=self.counters[name], tags=tags or {}, unit="count"
        )
        self.metrics.append(metric)
        self._persist_metric(metric)

    def set_gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Set a gauge value."""
        self.gauges[name] = value

        metric = PerformanceMetric(
            name=f"gauge.{name}",
            value=value,
            tags=tags or {},
        )
        self.metrics.append(metric)
        self._persist_metric(metric)

    def record_latency(self, operation: str, latency_ms: float) -> None:
        """Record operation latency."""
        metric = PerformanceMetric(
            name=f"latency.{operation}",
            value=latency_ms,
            unit="milliseconds",
            tags={"operation": operation},
        )
        self.metrics.append(metric)
        self._persist_metric(metric)

    def record_error(self, error_type: str, details: str) -> None:
        """Record an error occurrence."""
        self.increment_counter(f"errors.{error_type}", tags={"details": details[:100]})

    def get_summary(self, last_n_minutes: int = 60) -> dict[str, Any]:
        """Get summary of metrics for the last N minutes."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=last_n_minutes)
        recent_metrics = [m for m in self.metrics if m.timestamp > cutoff_time]

        summary = {
            "period_minutes": last_n_minutes,
            "total_metrics": len(recent_metrics),
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "active_timers": list(self.timers.keys()),
        }

        # Calculate timer statistics
        timer_metrics = [m for m in recent_metrics if m.name.startswith("timer.")]
        if timer_metrics:
            timer_values = [m.value for m in timer_metrics]
            summary["timer_stats"] = {
                "count": len(timer_values),
                "mean": np.mean(timer_values),
                "median": np.median(timer_values),
                "p95": np.percentile(timer_values, 95),
                "p99": np.percentile(timer_values, 99),
            }

        # Calculate error rate
        error_count = sum(1 for m in recent_metrics if "error" in m.name)
        summary["error_rate"] = error_count / max(1, len(recent_metrics))

        return summary

    def _persist_metric(self, metric: PerformanceMetric) -> None:
        """Persist metric to storage."""
        date_str = metric.timestamp.strftime("%Y%m%d")
        file_path = self.storage_path / f"metrics_{date_str}.jsonl"

        with open(file_path, "a") as f:
            f.write(metric.json() + "\n")


class PerformanceMonitor:
    """Monitor system and strategy performance."""

    def __init__(self):
        """Initialize performance monitor."""
        self.collector = MetricsCollector()
        self.thresholds = {
            "max_latency_ms": 1000,
            "max_error_rate": 0.05,
            "min_success_rate": 0.95,
            "max_memory_mb": 1024,
        }
        self.alerts: list[dict[str, Any]] = []

    def monitor_backtest(self, strategy: str, timerange: str) -> dict[str, Any]:
        """Monitor a backtest run."""
        self.collector.start_timer(f"backtest.{strategy}")
        self.collector.increment_counter("backtests.started", tags={"strategy": strategy})

        def on_complete(success: bool, metrics: dict | None = None):
            duration = self.collector.stop_timer(f"backtest.{strategy}")

            if success:
                self.collector.increment_counter("backtests.completed", tags={"strategy": strategy})
                if metrics:
                    self.collector.set_gauge(
                        f"backtest.profit.{strategy}", metrics.get("profit_total", 0)
                    )
                    self.collector.set_gauge(
                        f"backtest.trades.{strategy}", metrics.get("trades", 0)
                    )
            else:
                self.collector.increment_counter("backtests.failed", tags={"strategy": strategy})

            return {
                "strategy": strategy,
                "duration": duration,
                "success": success,
                "metrics": metrics,
            }

        return on_complete

    def monitor_live_trading(self, strategy: str) -> None:
        """Monitor live trading performance."""
        self.collector.increment_counter("live.sessions", tags={"strategy": strategy})

        def on_trade(trade_result: dict):
            self.collector.increment_counter("live.trades", tags={"strategy": strategy})

            if trade_result.get("profit", 0) > 0:
                self.collector.increment_counter("live.wins", tags={"strategy": strategy})
            else:
                self.collector.increment_counter("live.losses", tags={"strategy": strategy})

            self.collector.set_gauge(f"live.pnl.{strategy}", trade_result.get("total_profit", 0))

        return on_trade

    def check_thresholds(self) -> list[dict[str, Any]]:
        """Check if any thresholds are breached."""
        summary = self.collector.get_summary(last_n_minutes=5)
        alerts = []

        # Check error rate
        if summary["error_rate"] > self.thresholds["max_error_rate"]:
            alerts.append(
                {
                    "type": "error_rate",
                    "severity": "high",
                    "message": f"Error rate {summary['error_rate']:.2%} exceeds threshold",
                    "timestamp": datetime.utcnow(),
                }
            )

        # Check latency
        if "timer_stats" in summary:
            p99_latency = summary["timer_stats"]["p99"] * 1000  # Convert to ms
            if p99_latency > self.thresholds["max_latency_ms"]:
                alerts.append(
                    {
                        "type": "latency",
                        "severity": "medium",
                        "message": f"P99 latency {p99_latency:.0f}ms exceeds threshold",
                        "timestamp": datetime.utcnow(),
                    }
                )

        self.alerts.extend(alerts)
        return alerts

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get data for performance dashboard."""
        summary = self.collector.get_summary(last_n_minutes=60)

        return {
            "summary": summary,
            "alerts": self.alerts[-10:],  # Last 10 alerts
            "thresholds": self.thresholds,
            "timestamp": datetime.utcnow().isoformat(),
        }


class StrategyPerformanceTracker:
    """Track individual strategy performance over time."""

    def __init__(self, strategy_name: str):
        """Initialize tracker for a specific strategy."""
        self.strategy_name = strategy_name
        self.trades: list[dict] = []
        self.daily_pnl: list[float] = []
        self.metrics_history: list[dict] = []

    def record_trade(self, trade: dict) -> None:
        """Record a trade."""
        self.trades.append(
            {**trade, "timestamp": datetime.utcnow(), "strategy": self.strategy_name}
        )

    def calculate_metrics(self) -> dict[str, float]:
        """Calculate performance metrics."""
        if not self.trades:
            return {}

        profits = [t.get("profit", 0) for t in self.trades]

        metrics = {
            "total_trades": len(self.trades),
            "win_rate": sum(1 for p in profits if p > 0) / len(profits),
            "total_profit": sum(profits),
            "avg_profit": np.mean(profits),
            "max_drawdown": self._calculate_max_drawdown(profits),
            "sharpe_ratio": self._calculate_sharpe_ratio(profits),
            "profit_factor": self._calculate_profit_factor(profits),
        }

        self.metrics_history.append({**metrics, "timestamp": datetime.utcnow()})

        return metrics

    def _calculate_max_drawdown(self, profits: list[float]) -> float:
        """Calculate maximum drawdown."""
        cumsum = np.cumsum(profits)
        running_max = np.maximum.accumulate(cumsum)
        drawdown = (cumsum - running_max) / np.maximum(running_max, 1)
        return float(np.min(drawdown))

    def _calculate_sharpe_ratio(self, profits: list[float]) -> float:
        """Calculate Sharpe ratio."""
        if len(profits) < 2:
            return 0.0
        returns = np.array(profits)
        return float(np.mean(returns) / (np.std(returns) + 1e-10))

    def _calculate_profit_factor(self, profits: list[float]) -> float:
        """Calculate profit factor."""
        gains = sum(p for p in profits if p > 0)
        losses = abs(sum(p for p in profits if p < 0))
        return gains / max(losses, 1e-10)
