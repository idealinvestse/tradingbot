from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from .ai_executor import AIStrategyExecutor
from .metrics_collector import MetricsCollector as AIStrategyMetrics
from .ai_registry import AIStrategyRegistry
from .ai_storage import AIStrategyStorage
from .logging_utils import get_json_logger
from .risk import RiskManager


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    correlation_id: str | None = None


def _run(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int | None = None,
    *,
    correlation_id: str | None = None,
    env: dict[str, str] | None = None,
) -> RunResult:
    """Execute a command and capture output.

    Note: This is a thin wrapper. Callers should pass explicit arguments and avoid shell=True.
    """
    logger = get_json_logger(
        "runner",
        static_fields={"correlation_id": correlation_id} if correlation_id else {},
    )
    logger.debug("run_command", extra={"cmd": cmd, "cwd": str(cwd) if cwd else None})

    actual_env = os.environ.copy()
    if env:
        actual_env.update(env)

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=actual_env,
            shell=False,
        )
        return RunResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            correlation_id=correlation_id,
        )
    except subprocess.TimeoutExpired as e:
        logger.error("command_timeout", extra={"cmd": cmd, "timeout": timeout})
        return RunResult(
            returncode=1,
            stdout=str(e.stdout or "") if hasattr(e, "stdout") else "",
            stderr=str(e.stderr or "") if hasattr(e, "stderr") else "",
            correlation_id=correlation_id,
        )
    except Exception as e:
        logger.error("command_error", extra={"cmd": cmd, "error": str(e)})
        return RunResult(
            returncode=1,
            stdout="",
            stderr=str(e),
            correlation_id=correlation_id,
        )


async def run_ai_strategies(
    symbol: str = "BTC/USDT",
    *,
    strategy_type: str | None = None,
    market_data_path: Path | None = None,
    timeout: int = 300,
    correlation_id: str | None = None,
) -> dict:
    """Run AI strategies with risk management integration.

    Args:
        symbol: Trading pair symbol
        strategy_type: Optional specific strategy type to run
        market_data_path: Optional path to market data CSV
        timeout: Execution timeout in seconds
        correlation_id: Optional correlation ID for tracing

    Returns:
        Dictionary with execution results and metrics
    """
    import asyncio
    from datetime import datetime

    import pandas as pd

    cid = correlation_id or uuid.uuid4().hex
    logger = get_json_logger(
        "runner.ai",
        static_fields={
            "correlation_id": cid,
            "kind": "ai_strategy",
            "symbol": symbol,
            "strategy_type": strategy_type or "all",
        },
    )

    # Risk pre-checks
    rm = RiskManager()
    allowed, reason = rm.pre_run_check(
        kind="ai_strategy",
        strategy=strategy_type or "all_ai",
        timeframe="5m",
        context={"symbol": symbol},
        correlation_id=cid,
    )
    if not allowed:
        logger.warning("risk_block", extra={"reason": reason})
        return {
            "success": False,
            "error": f"Risk blocked: {reason}",
            "correlation_id": cid,
        }

    # Concurrency slot acquire
    slot_ok, slot_reason, lock_path = rm.acquire_run_slot(kind="ai_strategy", correlation_id=cid)
    if not slot_ok:
        logger.warning("risk_concurrency_block", extra={"reason": slot_reason})
        return {
            "success": False,
            "error": f"Risk concurrency blocked: {slot_reason}",
            "correlation_id": cid,
        }

    try:
        # Initialize AI components
        registry = AIStrategyRegistry()
        storage = AIStrategyStorage()
        metrics = AIStrategyMetrics()
        risk_manager = RiskManager()
        executor = AIStrategyExecutor(registry, risk_manager, metrics, storage)

        # Load or generate market data
        if market_data_path and market_data_path.exists():
            market_data = pd.read_csv(market_data_path)
            logger.info(
                "market_data_loaded",
                extra={"path": str(market_data_path), "rows": len(market_data)},
            )
        else:
            # Generate synthetic data for testing
            periods = 100
            dates = pd.date_range(end=datetime.utcnow(), periods=periods, freq="5min")
            base_price = 50000 if "BTC" in symbol else 3000
            market_data = pd.DataFrame(
                {
                    "date": dates,
                    "open": base_price
                    * (1 + pd.Series(range(periods)).apply(lambda x: (x % 10 - 5) / 100)),
                    "high": base_price
                    * (1 + pd.Series(range(periods)).apply(lambda x: (x % 10 - 3) / 100)),
                    "low": base_price
                    * (1 + pd.Series(range(periods)).apply(lambda x: (x % 10 - 7) / 100)),
                    "close": base_price
                    * (1 + pd.Series(range(periods)).apply(lambda x: (x % 10 - 4) / 100)),
                    "volume": 1000000 * (1 + pd.Series(range(periods)).apply(lambda x: x % 5 / 10)),
                }
            )
            logger.info("market_data_generated", extra={"periods": periods, "symbol": symbol})

        # Prepare context
        context = {
            "symbol": symbol,
            "exchange": "binance",
            "account_balance": 10000,
            "risk_per_trade": 0.02,
            "order_book_imbalance": 0.3,
            "spread_percentage": 0.5,
            "volatility": (
                market_data["close"].pct_change().std() if not market_data.empty else 0.02
            ),
            "volume_profile": market_data["volume"].mean() if not market_data.empty else 1000000,
            "correlation_id": cid,
        }

        # Execute strategies
        if strategy_type:
            # Run specific strategy type
            strategies = registry.get_by_type(strategy_type)
            if not strategies:
                logger.warning("no_strategies_found", extra={"type": strategy_type})
                return {
                    "success": False,
                    "error": f"No strategies found for type: {strategy_type}",
                    "correlation_id": cid,
                }
            results = await asyncio.gather(
                *[executor.execute_strategy(s, market_data, context) for s in strategies],
                return_exceptions=True,
            )
        else:
            # Run all enabled strategies
            exec_results = await executor.execute_all_strategies(market_data, context)
            results = list(exec_results)

        # Compile results
        successful = [r for r in results if not isinstance(r, Exception) and hasattr(r, "success") and r.success]
        failed = [r for r in results if isinstance(r, Exception) or (hasattr(r, "success") and not r.success)]

        # Get execution stats
        stats = executor.get_execution_stats()

        # Record metrics
        for result in successful:
            if hasattr(result, "signal") and result.signal:
                metrics.record_signal(
                    strategy_name=getattr(result, "strategy_name", ""),
                    signal=result.signal.dict() if result.signal else {},
                    correlation_id=getattr(result, "correlation_id", ""),
                )

        logger.info(
            "ai_strategies_complete",
            extra={
                "total": len(results),
                "successful": len(successful),
                "failed": len(failed),
                "avg_exec_time_ms": stats.get("avg_execution_time_ms", 0),
            },
        )

        return {
            "success": True,
            "correlation_id": cid,
            "total_strategies": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "signals_generated": sum(1 for r in successful if hasattr(r, "signal") and getattr(r, "signal", None) is not None),
            "execution_stats": stats,
            "results": [
                {
                    "strategy": getattr(r, "strategy_name", ""),
                    "type": (
                        r.strategy_type.value if hasattr(r, "strategy_type") and r.strategy_type is not None
                        else str(getattr(r, "strategy_type", None))
                    ),
                    "success": getattr(r, "success", False),
                    "signal": r.signal.dict() if hasattr(r, "signal") and r.signal is not None else None,
                    "error": getattr(r, "error", ""),
                    "execution_time_ms": getattr(r, "execution_time_ms", 0),
                }
                for r in results
                if not isinstance(r, Exception) and hasattr(r, "strategy_name")
            ],
        }

    except Exception as e:
        logger.error("ai_strategies_error", extra={"error": str(e)})
        return {
            "success": False,
            "error": str(e),
            "correlation_id": cid,
        }

    finally:
        rm.release_run_slot(lock_path, correlation_id=cid)
