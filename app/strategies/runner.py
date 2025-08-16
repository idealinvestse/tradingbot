from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str


def _run(cmd: List[str], cwd: Optional[Path] = None, timeout: Optional[int] = None) -> RunResult:
    """Execute a command and capture output.

    Note: This is a thin wrapper. Callers should pass explicit arguments and avoid shell=True.
    """
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return RunResult(proc.returncode, proc.stdout, proc.stderr)


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
) -> RunResult:
    cmd = build_freqtrade_backtest_cmd(
        config_path=config_path,
        strategy=strategy,
        timerange=timerange,
        pairs_file=pairs_file,
        timeframe=timeframe,
        addl_args=addl_args,
    )
    return _run(cmd, cwd=cwd, timeout=timeout)
