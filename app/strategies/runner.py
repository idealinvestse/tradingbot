from __future__ import annotations

import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .logging_utils import get_json_logger
from .risk import RiskManager


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    correlation_id: Optional[str] = None


def _run(
    cmd: List[str],
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    *,
    correlation_id: Optional[str] = None,
) -> RunResult:
    """Execute a command and capture output.

    Note: This is a thin wrapper. Callers should pass explicit arguments and avoid shell=True.
    """
    logger = get_json_logger(
        "runner",
        static_fields={"correlation_id": correlation_id} if correlation_id else None,
    )
    start = time.monotonic()
    logger.info(
        "exec_start",
        extra={
            "cmd": cmd,
            "cwd": str(cwd) if cwd else None,
            "timeout": timeout,
        },
    )
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    dur = time.monotonic() - start
    logger.info(
        "exec_end",
        extra={
            "returncode": proc.returncode,
            "duration_sec": dur,
        },
    )
    return RunResult(proc.returncode, proc.stdout, proc.stderr, correlation_id=correlation_id)


def build_freqtrade_backtest_cmd(
    config_path: Path,
    strategy: str,
    timerange: str,
    *,
    pairs_file: Optional[Path] = None,
    timeframe: Optional[str] = None,
    addl_args: Optional[Iterable[str]] = None,
) -> List[str]:
    """Construct a freqtrade backtest CLI command (local install).

    Example equivalent: freqtrade backtesting --config user_data/configs/config.bt.json --strategy MaCrossoverStrategy --timerange 20240101-20240701
    """
    logger = get_json_logger("runner.builder")
    logger.debug(
        "build_backtest_cmd",
        extra={
            "config_path": str(config_path),
            "strategy": strategy,
            "timerange": timerange,
            "pairs_file": str(pairs_file) if pairs_file else None,
            "timeframe": timeframe,
            "addl_args": list(addl_args) if addl_args else None,
        },
    )
    cmd: List[str] = [
        "freqtrade",
        "backtesting",
        "--config",
        str(config_path),
        "--strategy",
        strategy,
        "--timerange",
        timerange,
        "--export",
        "trades",
    ]
    if timeframe:
        cmd += ["--timeframe", timeframe]
    if pairs_file:
        cmd += ["--pairs-file", str(pairs_file)]
    if addl_args:
        cmd += list(addl_args)
    return cmd


def build_freqtrade_live_cmd(
    config_path: Path,
    *,
    strategy: Optional[str] = None,
    addl_args: Optional[Iterable[str]] = None,
) -> List[str]:
    """Construct a freqtrade live trade CLI command (local install).

    Example equivalent: freqtrade trade --config user_data/configs/config.mainnet.json --strategy MaCrossoverStrategy
    Strategy is optional and can be sourced from config.
    """
    logger = get_json_logger("runner.builder")
    logger.debug(
        "build_live_cmd",
        extra={
            "config_path": str(config_path),
            "strategy": strategy,
            "addl_args": list(addl_args) if addl_args else None,
        },
    )
    cmd: List[str] = [
        "freqtrade",
        "trade",
        "--config",
        str(config_path),
    ]
    if strategy:
        cmd += ["--strategy", strategy]
    if addl_args:
        cmd += list(addl_args)
    return cmd


def build_freqtrade_hyperopt_cmd(
    config_path: Path,
    strategy: str,
    spaces: List[str],
    epochs: int,
    *,
    timerange: Optional[str] = None,
    pairs_file: Optional[Path] = None,
    timeframe: Optional[str] = None,
    addl_args: Optional[Iterable[str]] = None,
) -> List[str]:
    """Construct a freqtrade hyperopt CLI command (local install).

    Example equivalent: freqtrade hyperopt --config user_data/configs/config.bt.json --strategy MaCrossoverStrategy --spaces buy sell roi stoploss --epochs 100
    """
    logger = get_json_logger("runner.builder")
    logger.debug(
        "build_hyperopt_cmd",
        extra={
            "config_path": str(config_path),
            "strategy": strategy,
            "spaces": spaces,
            "epochs": epochs,
            "timerange": timerange,
            "pairs_file": str(pairs_file) if pairs_file else None,
            "timeframe": timeframe,
            "addl_args": list(addl_args) if addl_args else None,
        },
    )
    cmd: List[str] = [
        "freqtrade",
        "hyperopt",
        "--config",
        str(config_path),
        "--strategy",
        strategy,
        "--spaces",
        " ".join(spaces),
        "--epochs",
        str(epochs),
    ]
    if timerange:
        cmd += ["--timerange", timerange]
    if timeframe:
        cmd += ["--timeframe", timeframe]
    if pairs_file:
        cmd += ["--pairs-file", str(pairs_file)]
    if addl_args:
        cmd += list(addl_args)
    return cmd


def run_live(
    config_path: Path,
    *,
    strategy: Optional[str] = None,
    addl_args: Optional[Iterable[str]] = None,
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    correlation_id: Optional[str] = None,
    open_trades_count: Optional[int] = None,
    market_exposure_pct: Optional[dict[str, float]] = None,
) -> RunResult:
    """Start a live trading process with pre-run RiskManager guardrails.

    Live guardrails are enforced via context:
    - open_trades_count: number of currently open trades
    - market_exposure_pct: mapping market-> exposure (0..1 or 0..100)
    """
    cid = correlation_id or uuid.uuid4().hex
    logger = get_json_logger(
        "runner",
        static_fields={
            "correlation_id": cid,
            "kind": "live",
            "strategy": strategy or "",
        },
    )
    logger.debug(
        "run_live_params",
        extra={
            "config_path": str(config_path),
            "addl_args": list(addl_args) if addl_args else None,
            "cwd": str(cwd) if cwd else None,
            "timeout": timeout,
            "open_trades_count": open_trades_count,
            "market_exposure_pct": market_exposure_pct,
        },
    )

    # Risk pre-checks
    rm = RiskManager()
    context = {
        "open_trades_count": open_trades_count,
        "market_exposure_pct": market_exposure_pct,
    }
    allowed, reason = rm.pre_run_check(
        kind="live", strategy=strategy or "", timeframe=None, context=context, correlation_id=cid
    )
    if not allowed:
        logger.warning("risk_block", extra={"reason": reason})
        return RunResult(1, "", f"Risk blocked: {reason}", correlation_id=cid)

    # Concurrency slot (unbounded for live by default, but keep for symmetry/logging)
    slot_ok, slot_reason, lock_path = rm.acquire_run_slot(kind="live", correlation_id=cid)
    if not slot_ok:
        logger.warning("risk_concurrency_block", extra={"reason": slot_reason})
        return RunResult(1, "", f"Risk concurrency blocked: {slot_reason}", correlation_id=cid)

    cmd = build_freqtrade_live_cmd(
        config_path=config_path,
        strategy=strategy,
        addl_args=addl_args,
    )
    logger.info("run_live_invoke", extra={"cmd": cmd})
    try:
        return _run(cmd, cwd=cwd, timeout=timeout, correlation_id=cid)
    finally:
        rm.release_run_slot(lock_path, correlation_id=cid)


def run_backtest(
    config_path: Path,
    strategy: str,
    timerange: str,
    *,
    pairs_file: Optional[Path] = None,
    timeframe: Optional[str] = None,
    addl_args: Optional[Iterable[str]] = None,
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> RunResult:
    cid = correlation_id or uuid.uuid4().hex
    logger = get_json_logger(
        "runner",
        static_fields={
            "correlation_id": cid,
            "kind": "backtest",
            "strategy": strategy,
            "timerange": timerange,
            "timeframe": timeframe or "",
        },
    )
    logger.debug(
        "run_backtest_params",
        extra={
            "config_path": str(config_path),
            "pairs_file": str(pairs_file) if pairs_file else None,
            "addl_args": list(addl_args) if addl_args else None,
            "cwd": str(cwd) if cwd else None,
            "timeout": timeout,
        },
    )

    # Risk pre-checks
    rm = RiskManager()
    allowed, reason = rm.pre_run_check(
        kind="backtest", strategy=strategy, timeframe=timeframe, context=None, correlation_id=cid
    )
    if not allowed:
        logger.warning("risk_block", extra={"reason": reason})
        return RunResult(1, "", f"Risk blocked: {reason}", correlation_id=cid)

    # Concurrency slot acquire
    slot_ok, slot_reason, lock_path = rm.acquire_run_slot(kind="backtest", correlation_id=cid)
    if not slot_ok:
        logger.warning("risk_concurrency_block", extra={"reason": slot_reason})
        return RunResult(1, "", f"Risk concurrency blocked: {slot_reason}", correlation_id=cid)

    cmd = build_freqtrade_backtest_cmd(
        config_path=config_path,
        strategy=strategy,
        timerange=timerange,
        pairs_file=pairs_file,
        timeframe=timeframe,
        addl_args=addl_args,
    )
    logger.info("run_backtest_invoke", extra={"cmd": cmd})
    try:
        return _run(cmd, cwd=cwd, timeout=timeout, correlation_id=cid)
    finally:
        rm.release_run_slot(lock_path, correlation_id=cid)


def run_hyperopt(
    config_path: Path,
    strategy: str,
    spaces: List[str],
    epochs: int,
    *,
    timerange: Optional[str] = None,
    pairs_file: Optional[Path] = None,
    timeframe: Optional[str] = None,
    addl_args: Optional[Iterable[str]] = None,
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> RunResult:
    cid = correlation_id or uuid.uuid4().hex
    logger = get_json_logger(
        "runner",
        static_fields={
            "correlation_id": cid,
            "kind": "hyperopt",
            "strategy": strategy,
            "spaces": " ".join(spaces),
            "epochs": epochs,
            "timerange": timerange or "",
            "timeframe": timeframe or "",
        },
    )
    logger.debug(
        "run_hyperopt_params",
        extra={
            "config_path": str(config_path),
            "pairs_file": str(pairs_file) if pairs_file else None,
            "addl_args": list(addl_args) if addl_args else None,
            "cwd": str(cwd) if cwd else None,
            "timeout": timeout,
        },
    )

    # Risk pre-checks
    rm = RiskManager()
    allowed, reason = rm.pre_run_check(
        kind="hyperopt", strategy=strategy, timeframe=timeframe, context=None, correlation_id=cid
    )
    if not allowed:
        logger.warning("risk_block", extra={"reason": reason})
        return RunResult(1, "", f"Risk blocked: {reason}", correlation_id=cid)

    # Concurrency slot acquire
    slot_ok, slot_reason, lock_path = rm.acquire_run_slot(kind="hyperopt", correlation_id=cid)
    if not slot_ok:
        logger.warning("risk_concurrency_block", extra={"reason": slot_reason})
        return RunResult(1, "", f"Risk concurrency blocked: {slot_reason}", correlation_id=cid)

    cmd = build_freqtrade_hyperopt_cmd(
        config_path=config_path,
        strategy=strategy,
        spaces=spaces,
        epochs=epochs,
        timerange=timerange,
        pairs_file=pairs_file,
        timeframe=timeframe,
        addl_args=addl_args,
    )
    logger.info("run_hyperopt_invoke", extra={"cmd": cmd})
    try:
        return _run(cmd, cwd=cwd, timeout=timeout, correlation_id=cid)
    finally:
        rm.release_run_slot(lock_path, correlation_id=cid)
