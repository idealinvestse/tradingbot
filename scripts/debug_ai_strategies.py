#!/usr/bin/env python3
"""Debug specific AI strategies."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ai_strategy_runner import AIStrategyRunner


async def debug_strategies() -> None:
    """Debug predictive_modeling and arbitrage strategies."""
    runner = AIStrategyRunner()

    # Get specific strategies
    strategies = list(runner.registry.strategies.values())
    predictive = next((s for s in strategies if s.strategy_type == "predictive_modeling"), None)
    arbitrage = next((s for s in strategies if s.strategy_type == "arbitrage"), None)

    if predictive:
        print(f"\n=== Testing Predictive Modeling: {predictive.name} ===")
        print(f"Config: {predictive}")

        market_data = runner.load_market_data("BTC/USDT")
        context = runner.prepare_context()

        result = await runner.executor.execute_strategy(predictive, market_data, context)
        print(f"Result: {result}")

    if arbitrage:
        print(f"\n=== Testing Arbitrage: {arbitrage.name} ===")
        print(f"Config: {arbitrage}")

        market_data = runner.load_market_data("BTC/USDT")
        context = runner.prepare_context()

        result = await runner.executor.execute_strategy(arbitrage, market_data, context)
        print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(debug_strategies())
