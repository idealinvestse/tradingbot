#!/usr/bin/env python3
"""AI Strategy Runner - Execute and monitor AI-powered trading strategies."""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from app.strategies.ai_executor import AIStrategyExecutor
from app.strategies.ai_metrics import AIMetricsTracker
from app.strategies.ai_registry import AIStrategyRegistry
from app.strategies.ai_storage import AIStrategyStorage
from app.strategies.metrics_collector import MetricsCollector
from app.strategies.risk import RiskManager
from app.strategies.utils import get_json_logger

logger = get_json_logger("ai_strategy_runner")


class AIStrategyRunner:
    """Runner for AI strategies."""

    def __init__(self, db_path: str = "user_data/backtest_results/index.db"):
        """Initialize the runner."""
        self.registry = AIStrategyRegistry()
        self.risk_manager = RiskManager()
        self.metrics_collector = MetricsCollector()
        self.metrics_tracker = AIMetricsTracker()
        self.storage = AIStrategyStorage(db_path)

        # Pass storage to executor
        self.executor = AIStrategyExecutor(
            registry=self.registry,
            risk_manager=self.risk_manager,
            metrics_collector=self.metrics_collector,
            storage=self.storage,
        )

    def load_market_data(self, symbol: str, timeframe: str = "5m") -> pd.DataFrame:
        """Load market data for testing."""
        # Simulate market data
        import numpy as np

        periods = 100
        dates = pd.date_range(end=datetime.utcnow(), periods=periods, freq=timeframe)

        # Generate realistic OHLCV data
        np.random.seed(42)
        close_prices = 50000 + np.cumsum(np.random.randn(periods) * 100)

        data = pd.DataFrame(
            {
                "date": dates,
                "open": close_prices + np.random.randn(periods) * 50,
                "high": close_prices + abs(np.random.randn(periods) * 100),
                "low": close_prices - abs(np.random.randn(periods) * 100),
                "close": close_prices,
                "volume": 1000 + np.random.randn(periods) * 100,
            }
        )

        return data

    def prepare_context(self) -> dict[str, Any]:
        """Prepare context data for strategy execution."""
        return {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "account_balance": 10000.0,
            "risk_percent": 2.0,
            "market_state": "normal",
            # Add data for different strategy types
            "sentiment_score": 0.7,  # For sentiment analysis
            "social_volume": 1500,
            "news_sentiment": 0.6,
            "order_book_imbalance": 0.3,  # For arbitrage
            "spread_percentage": 0.5,
            "volume_spike": True,  # For momentum
            "trending_narratives": ["AI", "DeFi"],  # For narrative detection
            "market_volatility": 0.25,
            "dca_threshold": -5.0,  # For DCA timing
            "portfolio_weights": {"BTC": 0.5, "ETH": 0.3, "SOL": 0.2},  # For rebalancing
            "current_weights": {"BTC": 0.4, "ETH": 0.3, "ADA": 0.2, "USDT": 0.1},
            "target_weights": {"BTC": 0.35, "ETH": 0.35, "ADA": 0.2, "USDT": 0.1},
            "spread": 0.0002,
            "order_imbalance": 0.15,
            "narrative_strength": 0.6,
            "trending_topics": ["AI coins", "DeFi 2.0", "Layer 2"],
        }

    async def run_single_strategy(self, strategy_name: str):
        """Run a single AI strategy."""
        # Get strategy from registry
        strategies = self.registry.get_enabled_strategies()
        strategy = next((s for s in strategies if strategy_name.lower() in s.name.lower()), None)

        if not strategy:
            logger.error(f"Strategy not found: {strategy_name}")
            return

        # Load market data and context
        market_data = self.load_market_data("BTC/USDT")
        context = self.prepare_context()

        # Execute strategy
        result = await self.executor.execute_strategy(strategy, market_data, context)

        if result.success:
            logger.info(f"Strategy executed successfully: {result.signal}")

            # Update metrics
            self.metrics_tracker.record_signal(
                strategy_name=strategy.name,
                strategy_type=strategy.strategy_type,
                signal_data=result.signal.dict() if result.signal else {},
                correlation_id=result.correlation_id,
            )

            # Simulate trade result
            if result.signal and result.signal.action != "hold":
                trade_result = {
                    "strategy_type": strategy.strategy_type.value,
                    "symbol": result.signal.symbol,
                    "side": result.signal.action,
                    "entry_price": result.signal.entry_price,
                    "exit_price": result.signal.entry_price * 1.02,  # 2% profit
                    "quantity": result.signal.suggested_size,
                    "pnl": result.signal.suggested_size * result.signal.entry_price * 0.02,
                    "pnl_percent": 2.0,
                    "fees": 0.001,
                    "success": True,
                    "opened_at": datetime.utcnow().isoformat(),
                    "closed_at": datetime.utcnow().isoformat(),
                }

                self.storage.save_trade_result(strategy.name, trade_result, result.correlation_id)

                self.metrics_tracker.record_trade_result(
                    strategy.name, trade_result, result.correlation_id
                )
        else:
            logger.warning(f"Strategy execution failed: {result.error}")

    async def run_all_strategies(self):
        """Run all enabled AI strategies."""
        market_data = self.load_market_data("BTC/USDT")
        context = self.prepare_context()

        results = await self.executor.execute_all_strategies(market_data, context)

        # Process results
        for result in results:
            if result.success and result.signal:
                # Update tracker
                self.metrics_tracker.record_signal(
                    strategy_name=result.strategy_name,
                    strategy_type=result.strategy_type,
                    signal_data=result.signal.dict(),
                    correlation_id=result.correlation_id,
                )

                # Update storage metrics
                metrics = self.metrics_tracker.metrics.get(result.strategy_name)
                if metrics:
                    self.storage.update_metrics(result.strategy_name, metrics.dict())

        # Generate summary
        summary = self.executor.get_execution_stats()
        logger.info(f"Execution summary: {json.dumps(summary, indent=2)}")

        return results

    def show_metrics(self, strategy_name: str = None):
        """Display metrics for strategies."""
        if strategy_name:
            report = self.metrics_tracker.get_strategy_report(strategy_name)
            print(f"\n{strategy_name} Metrics:")
            print(json.dumps(report, indent=2, default=str))
        else:
            summary = self.metrics_tracker.get_all_strategies_summary()
            print("\nAll Strategies Summary:")
            print(json.dumps(summary, indent=2, default=str))

            # Show database metrics
            db_metrics = self.storage.get_strategy_performance_summary()
            if db_metrics:
                print("\nDatabase Metrics:")
                for metric in db_metrics:
                    print(
                        f"  {metric['strategy_name']}: Return={metric['total_return']:.2f}, Win Rate={metric['win_rate']:.2%}"
                    )

    def list_strategies(self):
        """List all available strategies."""
        strategies = self.registry.get_enabled_strategies()
        print(f"\nAvailable AI Strategies ({len(strategies)}):\n")

        for i, strategy in enumerate(strategies, 1):
            print(f"{i}. {strategy.name}")
            print(f"   Type: {strategy.strategy_type.value}")
            print(f"   Description: {strategy.description}")
            print(f"   Effectiveness: {strategy.why_effective}")
            print(f"   Min Confidence: {strategy.min_confidence}")
            print(f"   Enabled: {strategy.enabled}")
            print()

    def export_strategies(self, output_file: str):
        """Export strategies to JSON file."""
        json_data = self.registry.export_strategies_json()

        with open(output_file, "w") as f:
            f.write(json_data)

        print(f"Exported strategies to {output_file}")

    def import_strategies(self, input_file: str):
        """Import strategies from JSON file."""
        with open(input_file) as f:
            json_data = f.read()

        count = self.registry.import_strategies_json(json_data)
        print(f"Imported {count} strategies from {input_file}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AI Strategy Runner")
    parser.add_argument(
        "command",
        choices=["run", "run-all", "list", "metrics", "export", "import"],
        help="Command to execute",
    )
    parser.add_argument("--strategy", "-s", help="Strategy name for single run")
    parser.add_argument("--file", "-f", help="File for export/import operations")
    parser.add_argument(
        "--db", "-d", default="user_data/backtest_results/index.db", help="Database path"
    )

    args = parser.parse_args()

    runner = AIStrategyRunner(args.db)

    if args.command == "list":
        runner.list_strategies()

    elif args.command == "run":
        if not args.strategy:
            print("Error: --strategy required for 'run' command")
            sys.exit(1)
        await runner.run_single_strategy(args.strategy)
        runner.show_metrics(args.strategy)

    elif args.command == "run-all":
        await runner.run_all_strategies()
        runner.show_metrics()

    elif args.command == "metrics":
        runner.show_metrics(args.strategy)

    elif args.command == "export":
        if not args.file:
            args.file = "ai_strategies_export.json"
        runner.export_strategies(args.file)

    elif args.command == "import":
        if not args.file:
            print("Error: --file required for 'import' command")
            sys.exit(1)
        runner.import_strategies(args.file)


if __name__ == "__main__":
    asyncio.run(main())
