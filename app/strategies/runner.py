from __future__ import annotations

import datetime
import json
import os
import gzip
import zipfile
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from app.data_services.news_fetcher import DemoNewsFetcher
from app.data_services.sentiment_analyzer import DemoSentimentAnalyzer
from app.strategies.persistence.sqlite import (
    connect,
    ensure_schema,
    upsert_news_articles,
)

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
    env: Optional[dict[str, str]] = None,
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
        env=env,
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
        sys.executable,
        "-m",
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
        sys.executable,
        "-m",
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
        sys.executable,
        "-m",
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


def _prepare_external_data(
    timerange: str,
    pairs: List[str],
    db_path: Path,
    *,
    correlation_id: Optional[str] = None,
):
    """Fetches, analyzes, and persists external data like news and sentiment."""
    logger = get_json_logger(
        "runner.data_prep",
        static_fields={"correlation_id": correlation_id} if correlation_id else None,
    )
    logger.info("Starting external data preparation.")

    try:
        start_str, end_str = timerange.split("-")
        since = datetime.datetime.strptime(start_str, "%Y%m%d").replace(
            tzinfo=datetime.timezone.utc
        )
        until = datetime.datetime.strptime(end_str, "%Y%m%d").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError as e:
        logger.error(
            "invalid_timerange_format", extra={"timerange": timerange, "error": str(e)}
        )
        return

    # 1. Fetch news
    news_fetcher = DemoNewsFetcher()
    articles = news_fetcher.fetch_news(symbols=pairs, since=since, until=until)
    if not articles:
        logger.info("No relevant news articles found for the given symbols and timerange.")
        return

    # 2. Analyze sentiment
    sentiment_analyzer = DemoSentimentAnalyzer()
    enriched_articles = sentiment_analyzer.analyze(articles)

    # 3. Persist to database
    try:
        conn = connect(db_path)
        ensure_schema(conn, with_extended=True)
        upsert_news_articles(conn, enriched_articles)
        logger.info(
            f"Successfully upserted {len(enriched_articles)} articles into the database.",
            extra={"db_path": str(db_path)},
        )
    except Exception as e:
        logger.error("db_persistence_failed", extra={"error": str(e)})
    finally:
        if 'conn' in locals() and conn:
            conn.close()


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
    db_path: Optional[Path] = None,
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
    # --- External Data Preparation ---
    # If a specific db_path is provided, we assume data is managed externally (e.g., in tests).
    if not db_path:
        final_db_path = Path.cwd() / "user_data" / "backtest_results" / "index.db"
        pairs_to_fetch = []
        if pairs_file and pairs_file.exists():
            with open(pairs_file, 'r') as f:
                pairs_to_fetch = [line.strip() for line in f if line.strip()]
        elif config_path and config_path.exists():
            with open(config_path, 'r') as f:
                config_data = json.load(f)
                pairs_to_fetch = config_data.get('exchange', {}).get('pair_whitelist', [])

        if pairs_to_fetch:
            _prepare_external_data(
                timerange=timerange,
                pairs=pairs_to_fetch,
                db_path=final_db_path,
                correlation_id=cid,
            )
        else:
            logger.warning("data_prep_skipped_no_pairs", extra={"reason": "No pairs found in pairs_file or config."})
    # --- End External Data Preparation ---

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

    # Determine export filename based on config to ensure deterministic location/name
    try:
        with open(config_path, "r") as cf:
            cfg = json.load(cf)
        export_dir_str = cfg.get("exportdir")
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("exportdir_read_failed", extra={"error": str(e)})
        export_dir_str = None
    export_dir = Path(export_dir_str) if export_dir_str else (Path.cwd() / "user_data" / "backtest_results")
    export_dir.mkdir(parents=True, exist_ok=True)
    export_filename = export_dir / "trades.json"
    extra_args: List[str] = list(addl_args) if addl_args else []
    # Ask freqtrade to export to our deterministic path
    extra_args += ["--export-filename", str(export_filename)]
    logger.debug(
        "export_plan",
        extra={"export_dir": str(export_dir), "export_filename": str(export_filename)},
    )

    cmd = build_freqtrade_backtest_cmd(
        config_path=config_path,
        strategy=strategy,
        timerange=timerange,
        pairs_file=pairs_file,
        timeframe=timeframe,
        addl_args=extra_args,
    )
    logger.info("run_backtest_invoke", extra={"cmd": cmd})
    try:
        # Ensure subprocess can import project modules even when cwd is a temp dir.
        env = os.environ.copy()
        try:
            project_root = Path(__file__).resolve().parents[2]
        except Exception:
            project_root = Path.cwd()
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(project_root) + (os.pathsep + existing_pp if existing_pp else "")
        res = _run(cmd, cwd=cwd, timeout=timeout, correlation_id=cid, env=env)
        # Log tail of subprocess output for diagnostics
        try:
            tail_len = 2000
            stdout_tail = res.stdout[-tail_len:] if res.stdout else ""
            stderr_tail = res.stderr[-tail_len:] if res.stderr else ""
            logger.info("subprocess_stdout_tail", extra={"tail": stdout_tail})
            if stderr_tail:
                logger.info("subprocess_stderr_tail", extra={"tail": stderr_tail})
        except Exception:
            pass
        # Fallback: If freqtrade exported a different filename, normalize to trades.json
        if res.returncode == 0 and not export_filename.exists():
            try:
                # consider both .json and .json.gz, pick the newest
                json_candidates = list(export_dir.glob("*.json"))
                gz_candidates = list(export_dir.glob("*.json.gz"))
                candidates = sorted(
                    json_candidates + gz_candidates,
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if candidates:
                    try:
                        logger.debug(
                            "export_candidates",
                            extra={"candidates": [str(p) for p in candidates[:5]]},
                        )
                    except Exception:
                        pass
                    src = candidates[0]
                    if src.suffixes[-2:] == [".json", ".gz"]:
                        # decompress
                        with gzip.open(src, "rt") as fin, open(export_filename, "w") as fout:
                            fout.write(fin.read())
                        logger.info(
                            "export_normalized",
                            extra={
                                "source": str(src),
                                "target": str(export_filename),
                                "mode": "decompressed",
                            },
                        )
                    else:
                        shutil.copyfile(src, export_filename)
                        logger.info(
                            "export_normalized",
                            extra={
                                "source": str(src),
                                "target": str(export_filename),
                                "mode": "copied",
                            },
                        )
                else:
                    logger.warning(
                        "export_missing",
                        extra={"export_dir": str(export_dir)},
                    )
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("export_postprocess_failed", extra={"error": str(e)})

        # Normalize JSON structure to {"trades": [...]}
        if res.returncode == 0 and export_filename.exists():
            try:
                with open(export_filename, "r") as jf:
                    data = json.load(jf)
                def is_trade_dict(d: dict) -> bool:
                    # Heuristic keys often present in freqtrade exports
                    keys = set(d.keys())
                    hints = {"pair", "open_date", "close_date", "profit_abs", "profit_ratio", "buy_tag", "open_rate"}
                    return len(keys & hints) >= 2

                def find_trades(obj):
                    if isinstance(obj, list):
                        if obj and isinstance(obj[0], dict) and is_trade_dict(obj[0]):
                            return obj
                        return None
                    if isinstance(obj, dict):
                        if "trades" in obj and isinstance(obj["trades"], list):
                            return obj["trades"]
                        for v in obj.values():
                            resv = find_trades(v)
                            if resv is not None:
                                return resv
                    return None

                trades_list = None
                if isinstance(data, list):
                    trades_list = data
                elif isinstance(data, dict):
                    trades_list = find_trades(data)

                if trades_list is not None:
                    with open(export_filename, "w") as jf:
                        json.dump({"trades": trades_list}, jf)
                    logger.info(
                        "export_schema_normalized",
                        extra={"path": str(export_filename), "count": len(trades_list)},
                    )
                else:
                    # Recovery: scan export_dir for a file that contains trades
                    def load_json_from_path(p: Path):
                        if p.suffixes[-2:] == [".json", ".gz"]:
                            with gzip.open(p, "rt") as f:
                                return json.load(f)
                        if p.suffix == ".json":
                            with open(p, "r") as f:
                                return json.load(f)
                        if p.suffix == ".zip":
                            try:
                                with zipfile.ZipFile(p) as zf:
                                    # try common file names first
                                    preferred = [
                                        "trades.json",
                                        "backtest-result.json",
                                        "result.json",
                                    ]
                                    names = zf.namelist()
                                    for name in preferred + names:
                                        if name in names and name.endswith(".json"):
                                            with zf.open(name) as fo:
                                                return json.loads(fo.read().decode("utf-8", errors="replace"))
                            except Exception:
                                return None
                        return None

                    cand_paths = sorted(
                        list(export_dir.glob("*.json"))
                        + list(export_dir.glob("*.json.gz"))
                        + list(export_dir.glob("*.zip")),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                    try:
                        logger.debug(
                            "recovery_candidates",
                            extra={"candidates": [str(p) for p in cand_paths[:10]]},
                        )
                    except Exception:
                        pass
                    recovered = False
                    for cp in cand_paths:
                        if cp.resolve() == export_filename.resolve():
                            continue
                        try:
                            obj = load_json_from_path(cp)
                            if obj is None:
                                continue
                            trades = None
                            if isinstance(obj, list):
                                trades = obj
                            elif isinstance(obj, dict):
                                trades = find_trades(obj)
                            if trades is not None:
                                with open(export_filename, "w") as jf:
                                    json.dump({"trades": trades}, jf)
                                logger.info(
                                    "export_schema_recovered",
                                    extra={"from": str(cp), "to": str(export_filename), "count": len(trades)},
                                )
                                recovered = True
                                break
                        except Exception:
                            continue

                    if not recovered:
                        # dump short head for debugging
                        try:
                            head = ""
                            with open(export_filename, "rb") as f:
                                head = f.read(512).decode("utf-8", errors="replace")
                        except Exception:
                            head = "<unreadable>"
                        logger.warning(
                            "export_schema_unexpected",
                            extra={"path": str(export_filename), "head": head},
                        )
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("export_schema_normalize_failed", extra={"error": str(e)})
        return res
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
