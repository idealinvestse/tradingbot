#!/usr/bin/env python3
"""Test AI strategies integration with runner.py"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.strategies.runner import run_ai_strategies


async def test_integration():
    """Test the AI strategies integration"""
    
    print("Testing AI strategies integration with runner.py...\n")
    
    # Test running all strategies
    print("1. Running all AI strategies...")
    result = await run_ai_strategies(
        symbol="BTC/USDT",
        timeout=30
    )
    
    if result["success"]:
        print(f"[OK] All strategies executed successfully")
        print(f"  - Total strategies: {result['total_strategies']}")
        print(f"  - Successful: {result['successful']}")
        print(f"  - Failed: {result['failed']}")
        print(f"  - Signals generated: {result['signals_generated']}")
        print(f"  - Correlation ID: {result['correlation_id']}")
    else:
        print(f"[FAIL] Execution failed: {result.get('error', 'Unknown error')}")
        print(f"  - Details: {result}")
        return False
    
    # Test running specific strategy type
    print("\n2. Running specific strategy type (predictive_modeling)...")
    result = await run_ai_strategies(
        symbol="ETH/USDT",
        strategy_type="predictive_modeling",
        timeout=30
    )
    
    if result["success"]:
        print(f"[OK] Predictive modeling strategy executed successfully")
        print(f"  - Total strategies: {result['total_strategies']}")
        print(f"  - Signals generated: {result['signals_generated']}")
    else:
        print(f"[FAIL] Execution failed: {result.get('error', 'Unknown error')}")
    
    # Test running another specific strategy type
    print("\n3. Running specific strategy type (arbitrage)...")
    result = await run_ai_strategies(
        symbol="BTC/USDT",
        strategy_type="arbitrage",
        timeout=30
    )
    
    if result["success"]:
        print(f"[OK] Arbitrage strategy executed successfully")
        print(f"  - Total strategies: {result['total_strategies']}")
        print(f"  - Signals generated: {result['signals_generated']}")
    else:
        print(f"[FAIL] Execution failed: {result.get('error', 'Unknown error')}")
    
    print("\n[OK] All integration tests completed successfully!")
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_integration())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
