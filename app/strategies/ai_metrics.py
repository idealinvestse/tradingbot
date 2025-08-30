"""AI Strategy Metrics Tracker for performance monitoring."""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from pydantic import BaseModel

from app.strategies.ai_registry import AIStrategyType
from app.strategies.utils import get_json_logger

logger = get_json_logger("ai_strategy_metrics")


class StrategyMetrics(BaseModel):
    """Metrics for a single AI strategy."""

    strategy_name: str
    strategy_type: AIStrategyType
    total_signals: int = 0
    successful_signals: int = 0
    failed_signals: int = 0
    avg_confidence: float = 0.0
    avg_return: float = 0.0
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_execution_time_ms: float = 0.0
    last_signal_time: datetime | None = None

    # Additional AI-specific metrics
    model_accuracy: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    sentiment_correlation: float = 0.0
    narrative_hit_rate: float = 0.0
    arbitrage_success_rate: float = 0.0
    grid_efficiency: float = 0.0
    momentum_capture_rate: float = 0.0
    rebalance_improvement: float = 0.0
    dca_cost_basis_improvement: float = 0.0
    hft_trade_frequency: float = 0.0

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class AIMetricsTracker:
    """Track and analyze AI strategy performance metrics."""

    def __init__(self) -> None:
        """Initialize metrics tracker."""
        self.metrics: dict[str, StrategyMetrics] = {}
        self.signal_history: list[dict[str, Any]] = []
        self.trade_history: list[dict[str, Any]] = []
        self.performance_snapshots: list[dict[str, Any]] = []

    def record_signal(
        self,
        strategy_name: str,
        strategy_type: AIStrategyType,
        signal_data: dict[str, Any],
        correlation_id: str,
    ) -> None:
        """Record a new signal from an AI strategy."""
        # Initialize metrics if needed
        if strategy_name not in self.metrics:
            self.metrics[strategy_name] = StrategyMetrics(
                strategy_name=strategy_name, strategy_type=strategy_type
            )

        metrics = self.metrics[strategy_name]

        # Update signal counts
        metrics.total_signals += 1
        metrics.last_signal_time = datetime.utcnow()

        # Update confidence metrics
        confidence = signal_data.get("confidence", 0.0)
        if metrics.avg_confidence == 0:
            metrics.avg_confidence = confidence
        else:
            metrics.avg_confidence = (
                metrics.avg_confidence * (metrics.total_signals - 1) + confidence
            ) / metrics.total_signals

        # Store signal in history
        self.signal_history.append(
            {
                "timestamp": datetime.utcnow(),
                "strategy_name": strategy_name,
                "strategy_type": strategy_type.value,
                "signal": signal_data,
                "correlation_id": correlation_id,
            }
        )

        logger.info(
            f"Recorded signal for {strategy_name}",
            extra={
                "correlation_id": correlation_id,
                "confidence": confidence,
                "action": signal_data.get("action"),
            },
        )

    def record_trade_result(
        self, strategy_name: str, trade_data: dict[str, Any], correlation_id: str
    ) -> None:
        """Record the result of a trade execution."""
        if strategy_name not in self.metrics:
            logger.warning(f"No metrics found for strategy: {strategy_name}")
            return

        metrics = self.metrics[strategy_name]

        # Update success/failure counts
        if trade_data.get("success", False):
            metrics.successful_signals += 1
        else:
            metrics.failed_signals += 1

        # Update return metrics
        pnl = trade_data.get("pnl", 0.0)
        if pnl != 0:
            if metrics.total_return == 0:
                metrics.total_return = pnl
            else:
                metrics.total_return += pnl

            # Update average return
            total_trades = metrics.successful_signals + metrics.failed_signals
            metrics.avg_return = metrics.total_return / total_trades if total_trades > 0 else 0

        # Calculate win rate
        total = metrics.successful_signals + metrics.failed_signals
        metrics.win_rate = metrics.successful_signals / total if total > 0 else 0

        # Store trade in history
        self.trade_history.append(
            {
                "timestamp": datetime.utcnow(),
                "strategy_name": strategy_name,
                "trade": trade_data,
                "correlation_id": correlation_id,
            }
        )

        logger.info(
            f"Recorded trade result for {strategy_name}",
            extra={
                "correlation_id": correlation_id,
                "success": trade_data.get("success"),
                "pnl": pnl,
            },
        )

    def update_strategy_specific_metrics(
        self, strategy_name: str, strategy_type: AIStrategyType, metrics_update: dict[str, float]
    ) -> None:
        """Update strategy-specific metrics."""
        if strategy_name not in self.metrics:
            self.metrics[strategy_name] = StrategyMetrics(
                strategy_name=strategy_name, strategy_type=strategy_type
            )

        metrics = self.metrics[strategy_name]

        # Update based on strategy type
        if strategy_type == AIStrategyType.SENTIMENT_ANALYSIS:
            if "sentiment_correlation" in metrics_update:
                metrics.sentiment_correlation = metrics_update["sentiment_correlation"]
            if "false_positive_rate" in metrics_update:
                metrics.false_positive_rate = metrics_update["false_positive_rate"]

        elif strategy_type == AIStrategyType.PREDICTIVE_MODELING:
            if "model_accuracy" in metrics_update:
                metrics.model_accuracy = metrics_update["model_accuracy"]

        elif strategy_type == AIStrategyType.ARBITRAGE:
            if "arbitrage_success_rate" in metrics_update:
                metrics.arbitrage_success_rate = metrics_update["arbitrage_success_rate"]

        elif strategy_type == AIStrategyType.GRID_TRADING:
            if "grid_efficiency" in metrics_update:
                metrics.grid_efficiency = metrics_update["grid_efficiency"]

        elif strategy_type == AIStrategyType.MOMENTUM_TRADING:
            if "momentum_capture_rate" in metrics_update:
                metrics.momentum_capture_rate = metrics_update["momentum_capture_rate"]

        elif strategy_type == AIStrategyType.PORTFOLIO_REBALANCING:
            if "rebalance_improvement" in metrics_update:
                metrics.rebalance_improvement = metrics_update["rebalance_improvement"]

        elif strategy_type == AIStrategyType.DCA_TIMING:
            if "dca_cost_basis_improvement" in metrics_update:
                metrics.dca_cost_basis_improvement = metrics_update["dca_cost_basis_improvement"]

        elif strategy_type == AIStrategyType.HIGH_FREQUENCY_TRADING:
            if "hft_trade_frequency" in metrics_update:
                metrics.hft_trade_frequency = metrics_update["hft_trade_frequency"]

        elif strategy_type == AIStrategyType.NARRATIVE_DETECTION:
            if "narrative_hit_rate" in metrics_update:
                metrics.narrative_hit_rate = metrics_update["narrative_hit_rate"]

        logger.debug(f"Updated specific metrics for {strategy_name}: {metrics_update}")

    def calculate_advanced_metrics(self, strategy_name: str) -> dict[str, float]:
        """Calculate advanced performance metrics."""
        if strategy_name not in self.metrics:
            return {}

        # Get trade history for this strategy
        strategy_trades = [t for t in self.trade_history if t["strategy_name"] == strategy_name]

        if not strategy_trades:
            return {}

        # Extract returns
        returns = [t["trade"].get("pnl", 0) for t in strategy_trades]
        returns_series = pd.Series(returns)

        # Calculate Sharpe ratio
        if len(returns) > 1 and returns_series.std() > 0:
            sharpe_ratio = (returns_series.mean() / returns_series.std()) * (252**0.5)
        else:
            sharpe_ratio = 0

        # Calculate max drawdown
        cumulative = returns_series.cumsum()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max.abs()
        max_drawdown = drawdown.min() if len(drawdown) > 0 else 0

        # Calculate profit factor
        wins = returns_series[returns_series > 0].sum()
        losses = abs(returns_series[returns_series < 0].sum())
        profit_factor = wins / losses if losses > 0 else float("inf")

        # Update metrics
        metrics = self.metrics[strategy_name]
        metrics.sharpe_ratio = float(sharpe_ratio)
        metrics.max_drawdown = float(max_drawdown)
        metrics.profit_factor = float(profit_factor)

        return {
            "sharpe_ratio": float(sharpe_ratio),
            "max_drawdown": float(max_drawdown),
            "profit_factor": float(profit_factor),
        }

    def get_strategy_report(self, strategy_name: str) -> dict[str, Any]:
        """Generate comprehensive report for a strategy."""
        if strategy_name not in self.metrics:
            return {"error": f"No metrics found for {strategy_name}"}

        metrics = self.metrics[strategy_name]
        advanced_metrics = self.calculate_advanced_metrics(strategy_name)

        return {
            "strategy_name": strategy_name,
            "strategy_type": metrics.strategy_type.value,
            "performance": {
                "total_signals": metrics.total_signals,
                "successful": metrics.successful_signals,
                "failed": metrics.failed_signals,
                "win_rate": f"{metrics.win_rate:.2%}",
                "avg_confidence": f"{metrics.avg_confidence:.2f}",
                "total_return": f"{metrics.total_return:.2f}",
                "avg_return": f"{metrics.avg_return:.2f}",
                "sharpe_ratio": f"{advanced_metrics.get('sharpe_ratio', 0):.2f}",
                "max_drawdown": f"{advanced_metrics.get('max_drawdown', 0):.2%}",
                "profit_factor": f"{advanced_metrics.get('profit_factor', 0):.2f}",
            },
            "ai_specific_metrics": self._get_ai_specific_metrics(metrics),
            "last_signal": (
                metrics.last_signal_time.isoformat() if metrics.last_signal_time else None
            ),
        }

    def _get_ai_specific_metrics(self, metrics: StrategyMetrics) -> dict[str, Any]:
        """Get AI-specific metrics based on strategy type."""
        specific = {}

        if metrics.strategy_type == AIStrategyType.SENTIMENT_ANALYSIS:
            if metrics.sentiment_correlation != 0:
                specific["sentiment_correlation"] = f"{metrics.sentiment_correlation:.2f}"
            if metrics.false_positive_rate != 0:
                specific["false_positive_rate"] = f"{metrics.false_positive_rate:.2%}"

        elif metrics.strategy_type == AIStrategyType.PREDICTIVE_MODELING:
            if metrics.model_accuracy != 0:
                specific["model_accuracy"] = f"{metrics.model_accuracy:.2%}"

        elif metrics.strategy_type == AIStrategyType.ARBITRAGE:
            if metrics.arbitrage_success_rate != 0:
                specific["arbitrage_success_rate"] = f"{metrics.arbitrage_success_rate:.2%}"

        elif metrics.strategy_type == AIStrategyType.GRID_TRADING:
            if metrics.grid_efficiency != 0:
                specific["grid_efficiency"] = f"{metrics.grid_efficiency:.2%}"

        elif metrics.strategy_type == AIStrategyType.MOMENTUM_TRADING:
            if metrics.momentum_capture_rate != 0:
                specific["momentum_capture_rate"] = f"{metrics.momentum_capture_rate:.2%}"

        elif metrics.strategy_type == AIStrategyType.PORTFOLIO_REBALANCING:
            if metrics.rebalance_improvement != 0:
                specific["rebalance_improvement"] = f"{metrics.rebalance_improvement:.2%}"

        elif metrics.strategy_type == AIStrategyType.DCA_TIMING:
            if metrics.dca_cost_basis_improvement != 0:
                specific["dca_cost_basis_improvement"] = f"{metrics.dca_cost_basis_improvement:.2%}"

        elif metrics.strategy_type == AIStrategyType.HIGH_FREQUENCY_TRADING:
            if metrics.hft_trade_frequency != 0:
                specific["hft_trade_frequency"] = f"{metrics.hft_trade_frequency:.0f} trades/hour"

        elif metrics.strategy_type == AIStrategyType.NARRATIVE_DETECTION:
            if metrics.narrative_hit_rate != 0:
                specific["narrative_hit_rate"] = f"{metrics.narrative_hit_rate:.2%}"

        return specific

    def get_all_strategies_summary(self) -> list[dict[str, Any]]:
        """Get summary of all tracked strategies."""
        summaries = []

        for strategy_name, metrics in self.metrics.items():
            summary = {
                "strategy": strategy_name,
                "type": metrics.strategy_type.value,
                "signals": metrics.total_signals,
                "win_rate": f"{metrics.win_rate:.2%}",
                "total_return": f"{metrics.total_return:.2f}",
                "last_signal": (
                    metrics.last_signal_time.isoformat() if metrics.last_signal_time else "Never"
                ),
            }
            summaries.append(summary)

        return summaries

    def export_metrics_json(self) -> str:
        """Export all metrics as JSON."""
        export_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "strategies": {},
            "summary": {
                "total_strategies": len(self.metrics),
                "total_signals": sum(m.total_signals for m in self.metrics.values()),
                "total_trades": len(self.trade_history),
            },
        }

        for strategy_name, metrics in self.metrics.items():
            export_data["strategies"][strategy_name] = self.get_strategy_report(strategy_name)

        return json.dumps(export_data, indent=2, default=str)

    def take_performance_snapshot(self) -> None:
        """Take a snapshot of current performance."""
        snapshot = {
            "timestamp": datetime.utcnow(),
            "metrics": {name: metrics.dict() for name, metrics in self.metrics.items()},
            "summary": self.get_all_strategies_summary(),
        }

        self.performance_snapshots.append(snapshot)
        logger.info(f"Performance snapshot taken at {snapshot['timestamp']}")

    def get_performance_trend(self, strategy_name: str, lookback_days: int = 7) -> dict[str, Any]:
        """Analyze performance trend over time."""
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)

        # Filter recent trades
        recent_trades = [
            t
            for t in self.trade_history
            if t["strategy_name"] == strategy_name and t["timestamp"] > cutoff
        ]

        if not recent_trades:
            return {"error": "No recent trades found"}

        # Group by day
        daily_performance = defaultdict(list)
        for trade in recent_trades:
            day = trade["timestamp"].date()
            pnl = trade["trade"].get("pnl", 0)
            daily_performance[day].append(pnl)

        # Calculate daily statistics
        trend = []
        for day, returns in sorted(daily_performance.items()):
            trend.append(
                {
                    "date": day.isoformat(),
                    "trades": len(returns),
                    "total_return": sum(returns),
                    "avg_return": sum(returns) / len(returns) if returns else 0,
                }
            )

        return {"strategy": strategy_name, "period": f"{lookback_days} days", "trend": trend}
