from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .logging_utils import get_json_logger
from .persistence.sqlite import connect, ensure_schema

UTC = timezone.utc


@dataclass
class BacktestMeta:
    strategy_class: str
    run_id: str
    timeframe: str | None
    start_ts: int | None
    end_ts: int | None

    @property
    def start_iso(self) -> str | None:
        if self.start_ts is None:
            return None
        return datetime.fromtimestamp(self.start_ts, tz=UTC).isoformat()

    @property
    def end_iso(self) -> str | None:
        if self.end_ts is None:
            return None
        return datetime.fromtimestamp(self.end_ts, tz=UTC).isoformat()


def _sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parse_backtest_meta(meta_path: Path) -> BacktestMeta | None:
    logger = get_json_logger("metrics", static_fields={"op": "parse_backtest_meta"})
    try:
        data = json.loads(meta_path.read_text(encoding='utf-8'))
    except Exception as e:
        logger.warning("meta_parse_error", extra={"path": str(meta_path), "error": str(e)})
        return None

    if not isinstance(data, dict) or not data:
        return None

    # Structure observed: {"ClassName": { ... entries ... }}
    strat_class = next(iter(data.keys()))
    payload = data[strat_class]

    # Optional validation via Pydantic if available
    _ok, _reason = _validate_backtest_payload(payload)
    if not _ok:
        logger.warning("meta_validation_failed", extra={"path": str(meta_path), "reason": _reason})
        return None

    return BacktestMeta(
        strategy_class=str(strat_class),
        run_id=str(payload.get('run_id')) if payload.get('run_id') else meta_path.stem,
        timeframe=payload.get('timeframe'),
        start_ts=payload.get('backtest_start_ts'),
        end_ts=payload.get('backtest_end_ts'),
    )


def _upsert_experiment(cur, exp_id: str, idea_id: str, strategy_id: str, timeframe: str | None, start_iso: str | None, end_iso: str | None, config_hash: str | None = None) -> None:
    logger = get_json_logger("metrics", static_fields={"op": "_upsert_experiment"})
    logger.debug("upserting_experiment", extra={"exp_id": exp_id, "strategy_id": strategy_id})
    cur.execute(
        """
        INSERT INTO experiments (
            id, idea_id, strategy_id, hypothesis, timeframe, markets, period_start_utc, period_end_utc, seed, config_hash, created_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            timeframe=excluded.timeframe,
            period_start_utc=excluded.period_start_utc,
            period_end_utc=excluded.period_end_utc,
            config_hash=excluded.config_hash
        """,
        (
            exp_id,
            idea_id,
            strategy_id,
            "auto-generated from backtest artifacts",
            timeframe or "",
            "",
            start_iso or "",
            end_iso or "",
            config_hash or "",
        ),
    )


def _upsert_run(cur, run_id: str, experiment_id: str, kind: str, started_iso: str | None, finished_iso: str | None, status: str, artifacts_path: str | None, data_window: str | None = None) -> None:
    logger = get_json_logger("metrics", static_fields={"op": "_upsert_run"})
    logger.debug("upserting_run", extra={"run_id": run_id, "kind": kind, "status": status})
    cur.execute(
        """
        INSERT INTO runs (
            id, experiment_id, kind, started_utc, finished_utc, status, docker_image, freqtrade_version, config_json, data_window, artifacts_path
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            experiment_id=excluded.experiment_id,
            kind=excluded.kind,
            started_utc=excluded.started_utc,
            finished_utc=excluded.finished_utc,
            status=excluded.status,
            data_window=excluded.data_window,
            artifacts_path=excluded.artifacts_path
        """,
        (
            run_id,
            experiment_id,
            kind,
            started_iso or "",
            finished_iso or "",
            status,
            data_window or "",
            artifacts_path,
        ),
    )


def _upsert_metric(cur, run_id: str, key: str, value: float) -> None:
    logger = get_json_logger("metrics", static_fields={"op": "_upsert_metric"})
    logger.debug("upserting_metric", extra={"run_id": run_id, "key": key, "value": value})
    # Use Decimal for monetary values to maintain precision
    # Quantize to 8 decimal places to match the precision used in _parse_zip_metrics
    # Only cast to float at the DB boundary as the schema uses REAL
    decimal_value = Decimal(str(value)).quantize(Decimal('0.00000001'))
    cur.execute(
        """
        INSERT INTO metrics (run_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT(run_id, key) DO UPDATE SET
            value=excluded.value
        """,
        (run_id, key, float(decimal_value)),
    )


def _upsert_artifact(cur, run_id: str, name: str, path: str, sha256: str | None) -> None:
    logger = get_json_logger("metrics", static_fields={"op": "_upsert_artifact"})
    logger.debug("upserting_artifact", extra={"run_id": run_id, "name": name, "sha256": sha256 or ''})
    cur.execute(
        """
        INSERT INTO artifacts (run_id, name, path, sha256)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(run_id, name) DO UPDATE SET
            path=excluded.path,
            sha256=excluded.sha256
        """,
        (run_id, name, path, sha256 or ""),
    )


def _parse_zip_metrics(zip_path: Path) -> dict[str, float]:
    """Extract key metrics from a Freqtrade backtest ZIP.

    Looks for the main summary JSON inside the ZIP (excludes *_config.json and *_Strategy.json).
    Returns a flat dict of metric_name -> float.
    """
    out: dict[str, float] = {}
    try:
        with zipfile.ZipFile(zip_path) as zf:
            # Find main JSON result
            names = [n for n in zf.namelist() if n.endswith('.json') and '_config' not in n and '_Strategy' not in n]
            if not names:
                return out
            data = json.loads(zf.read(names[0]).decode('utf-8'))

            # strategy section: {strategy_name: {...}}
            strat = data.get('strategy')
            if isinstance(strat, dict) and strat:
                strat_name = next(iter(strat.keys()))
                sd = strat.get(strat_name, {})
                if isinstance(sd, dict):
                    # Use Decimal for monetary values to maintain precision internally
                    # Only cast to float at the end for DB storage
                    monetary_keys = ('profit_total', 'profit_total_abs', 'profit_mean', 'profit_median',
                                   'cagr', 'expectancy', 'expectancy_ratio', 'market_change')

                    for k in monetary_keys:
                        v = sd.get(k)
                        if isinstance(v, (int, float)):
                            # Use Decimal for precision, then convert to float for DB storage
                            decimal_v = Decimal(str(v)).quantize(Decimal('0.00000001'))
                            out[k] = float(decimal_v)

                    # Non-monetary keys that can remain as regular floats
                    for k in ('sortino', 'sharpe', 'calmar', 'sqn', 'profit_factor',
                             'trades_per_day'):
                        v = sd.get(k)
                        if isinstance(v, (int, float)):
                            out[k] = float(v)

                    # total_trades
                    tt = sd.get('total_trades') or sd.get('trades')
                    if isinstance(tt, (int, float)):
                        out['trades'] = float(tt)

            # strategy_comparison: list of per-strategy summaries
            comp = data.get('strategy_comparison')
            if isinstance(comp, list) and comp:
                # pick matching strategy by 'key' if possible, else first
                chosen = None
                if isinstance(strat, dict) and strat:
                    strat_name = next(iter(strat.keys()))
                    for item in comp:
                        if isinstance(item, dict) and item.get('key') == strat_name:
                            chosen = item
                            break
                if chosen is None and isinstance(comp[0], dict):
                    chosen = comp[0]
                if isinstance(chosen, dict):
                    # Use Decimal for monetary values to maintain precision internally
                    # Only cast to float at the end for DB storage
                    monetary_keys = ('profit_total', 'profit_total_abs', 'profit_mean',
                                   'profit_total_pct', 'max_drawdown_account', 'max_drawdown_abs')

                    for k in monetary_keys:
                        v = chosen.get(k)
                        if isinstance(v, (int, float)):
                            # Use Decimal for precision, then convert to float for DB storage
                            decimal_v = Decimal(str(v)).quantize(Decimal('0.00000001'))
                            out[k] = float(decimal_v)

                    # Non-monetary keys that can remain as regular floats
                    for k in ('wins', 'losses', 'draws', 'winrate', 'duration_avg', 'sortino',
                             'sharpe', 'calmar', 'sqn', 'profit_factor', 'trades'):
                        v = chosen.get(k)
                        if isinstance(v, (int, float)):
                            out[k] = float(v)
    except Exception:
        # best-effort extraction; ignore errors and return what we found
        return out
    return out


def index_backtests(backtests_dir: Path, db_path: Path) -> int:
    """Parse all *.meta.json in backtests_dir and persist to SQLite.

    Returns number of indexed runs.
    """
    cid = uuid.uuid4().hex
    logger = get_json_logger(
        "metrics",
        static_fields={"correlation_id": cid, "op": "index_backtests"},
    )
    conn = connect(db_path)
    ensure_schema(conn, with_extended=True)
    cur = conn.cursor()

    count = 0
    meta_invalid_count = 0
    for meta_path in sorted(backtests_dir.glob("*.meta.json")):
        logger.info("scan_meta", extra={"path": str(meta_path)})
        t0 = time.perf_counter()
        meta = parse_backtest_meta(meta_path)
        if not meta:
            logger.warning("meta_invalid", extra={"path": str(meta_path)})
            meta_invalid_count += 1
            continue

        # Create synthetic IDs to tie together minimal experiment/run lineage
        strategy_id = meta.strategy_class  # if registry uses IDs differently, this is a placeholder
        exp_id = f"exp:{strategy_id}:{meta.timeframe or ''}:{meta.start_ts or ''}-{meta.end_ts or ''}"
        # Try to discover config hash inside ZIP (if present)
        config_hash: str | None = None
        zip_candidate = meta_path.with_suffix(".zip")
        if not zip_candidate.exists():
            prefix = meta_path.name.rsplit(".meta.json", 1)[0]
            zips = list(meta_path.parent.glob(prefix + "*.zip"))
            if zips:
                zip_candidate = zips[0]
        if zip_candidate.exists():
            try:
                with zipfile.ZipFile(zip_candidate) as zf:
                    cfg_names = [n for n in zf.namelist() if n.endswith("_config.json")]
                    if cfg_names:
                        cfg_bytes = zf.read(cfg_names[0])
                        config_hash = hashlib.sha256(cfg_bytes).hexdigest()
            except Exception:
                # best-effort only
                config_hash = None

        _upsert_experiment(
            cur,
            exp_id,
            idea_id=f"idea:auto:{strategy_id}",
            strategy_id=strategy_id,
            timeframe=meta.timeframe,
            start_iso=meta.start_iso,
            end_iso=meta.end_iso,
            config_hash=config_hash,
        )

        # Run record
        artifacts_dir = str(meta_path.parent)
        data_window = None
        if meta.start_iso and meta.end_iso:
            data_window = f"{meta.start_iso}..{meta.end_iso}"
        _upsert_run(
            cur,
            meta.run_id,
            experiment_id=exp_id,
            kind="backtest",
            started_iso=meta.start_iso,
            finished_iso=meta.end_iso,
            status="completed",
            artifacts_path=artifacts_dir,
            data_window=data_window,
        )

        # Minimal metrics we can infer now
        if meta.start_ts is not None and meta.end_ts is not None:
            _upsert_metric(cur, meta.run_id, "window_days", (meta.end_ts - meta.start_ts) / 86400.0)
        if meta.timeframe:
            _upsert_metric(cur, meta.run_id, "timeframe_minutes", _timeframe_to_minutes(meta.timeframe))

        # Artifacts: link meta json and potential zip with sha256
        _upsert_artifact(cur, meta.run_id, name=meta_path.name, path=str(meta_path), sha256=_sha256_file(meta_path))
        zip_candidate = meta_path.with_suffix(".zip")
        if not zip_candidate.exists():
            # Some files may include timestamps in names; try glob by stem prefix
            prefix = meta_path.name.rsplit(".meta.json", 1)[0]
            zips = list(meta_path.parent.glob(prefix + "*.zip"))
            if zips:
                zip_candidate = zips[0]
        if zip_candidate.exists():
            _upsert_artifact(cur, meta.run_id, name=zip_candidate.name, path=str(zip_candidate), sha256=_sha256_file(zip_candidate))
            # Parse and upsert detailed metrics from ZIP summary JSON
            metrics = _parse_zip_metrics(zip_candidate)
            for k, v in metrics.items():
                _upsert_metric(cur, meta.run_id, k, v)

        # Per-run parse latency in milliseconds
        dt_ms = (time.perf_counter() - t0) * 1000.0
        _upsert_metric(cur, meta.run_id, "parse_ms", dt_ms)

        count += 1
        logger.info("meta_indexed", extra={"run_id": meta.run_id})

    conn.commit()
    conn.close()
    logger.info("index_done", extra={"count": count, "db_path": str(db_path), "meta_invalid": meta_invalid_count})
    return count


def _timeframe_to_minutes(tf: str) -> float:
    tf = tf.strip().lower()
    if tf.endswith("m"):
        return float(tf[:-1])
    if tf.endswith("h"):
        return float(tf[:-1]) * 60.0
    if tf.endswith("d"):
        return float(tf[:-1]) * 60.0 * 24.0
    # default fallback
    return 0.0


def index_hyperopts(hyperopt_dir: Path, db_path: Path) -> int:
    """Parse all *.fthypt hyperopt result files and persist trials to SQLite.

    Each line in a .fthypt file is a JSON object for a trial, with keys such as
    'loss', 'params_dict', and optionally 'results_metrics'.
    We write one row in `runs` per trial (kind='hyperopt') and store numeric params
    as metrics with prefix 'param.' along with 'loss' and 'trades' (if available).
    """
    cid = uuid.uuid4().hex
    logger = get_json_logger(
        "metrics",
        static_fields={"correlation_id": cid, "op": "index_hyperopts"},
    )
    conn = connect(db_path)
    ensure_schema(conn, with_extended=True)
    cur = conn.cursor()

    ts_re = re.compile(r"_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})\\.fthypt$")

    count = 0
    trial_json_error_count = 0
    trial_invalid_count = 0
    file_parse_error_count = 0
    for f in sorted(hyperopt_dir.glob("*.fthypt")):
        logger.info("scan_fthypt", extra={"path": str(f)})
        name = f.name
        m = ts_re.search(name)
        if not m:
            # Fallback: use file stem as timestamp id
            ts_id = f.stem
            strat_cls = name.replace("strategy_", "").split("_", 1)[0]
        else:
            date_s, time_s = m.groups()
            ts_id = f"{date_s}_{time_s}"
            # strategy_<Class>_<date>_<time>.fthypt -> extract Class
            head = name[: m.start()]  # up to _YYYY-..
            # remove trailing underscore
            head = head[:-1] if head.endswith("_") else head
            strat_cls = head.replace("strategy_", "")

        # Experiment per file
        exp_id = f"exp:hyperopt:{strat_cls}:{ts_id}"
        _upsert_experiment(
            cur,
            exp_id=exp_id,
            idea_id=f"idea:auto:{strat_cls}",
            strategy_id=strat_cls,
            timeframe=None,
            start_iso=None,
            end_iso=None,
        )

        # Artifact: the hyperopt results file (link once per first trial via a flag)
        file_sha = _sha256_file(f)
        file_artifact_added = False

        # Use file mtimes as rough run timestamps
        t_iso = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC).isoformat()

        # Iterate lines (one JSON per trial)
        try:
            with f.open("r", encoding="utf-8") as fh:
                trial_idx = 0
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    t0 = time.perf_counter()
                    try:
                        rec = json.loads(line)
                    except Exception:
                        logger.warning("trial_json_error", extra={"file": name})
                        trial_json_error_count += 1
                        continue

                    # Optional validation
                    if not _validate_hyperopt_trial(rec):
                        logger.warning("trial_invalid", extra={"file": name})
                        trial_invalid_count += 1
                        continue

                    trial_idx += 1
                    run_id = f"hp:{strat_cls}:{ts_id}:{trial_idx:05d}"
                    _upsert_run(
                        cur,
                        run_id,
                        experiment_id=exp_id,
                        kind="hyperopt",
                        started_iso=t_iso,
                        finished_iso=t_iso,
                        status="completed",
                        artifacts_path=str(f.parent),
                        data_window=None,
                    )

                    # metrics: loss
                    loss = rec.get("loss")
                    if isinstance(loss, (int, float)):
                        _upsert_metric(cur, run_id, "loss", float(loss))

                    # metrics: params
                    p = rec.get("params_dict") or {}
                    if isinstance(p, dict):
                        for k, v in p.items():
                            if isinstance(v, bool):
                                _upsert_metric(cur, run_id, f"param.{k}", 1.0 if v else 0.0)
                            elif isinstance(v, (int, float)):
                                _upsert_metric(cur, run_id, f"param.{k}", float(v))

                    # metrics: results_metrics -> trades count if available
                    rm = rec.get("results_metrics") or {}
                    if isinstance(rm, dict):
                        trades = rm.get("trades")
                        if isinstance(trades, list):
                            _upsert_metric(cur, run_id, "trades", float(len(trades)))

                    # artifact link (once per file)
                    if not file_artifact_added:
                        _upsert_artifact(cur, run_id, name=name, path=str(f), sha256=file_sha)
                        file_artifact_added = True

                    # Per-run parse latency in milliseconds
                    dt_ms = (time.perf_counter() - t0) * 1000.0
                    _upsert_metric(cur, run_id, "parse_ms", dt_ms)

                    count += 1
        except Exception:
            # best-effort parsing per file
            logger.warning("file_parse_error", extra={"path": str(f)})
            file_parse_error_count += 1
            continue

    conn.commit()
    conn.close()
    logger.info("index_done", extra={"count": count, "db_path": str(db_path)})
    return count


# ---- Optional Pydantic validation helpers ----
try:
    from pydantic import BaseModel
    try:
        from pydantic import ConfigDict, model_validator  # v2
        _PYD_V2 = True
    except Exception:  # pragma: no cover - depends on pydantic version
        _PYD_V2 = False
        from pydantic import Extra, validator  # type: ignore

    if _PYD_V2:
        class _BacktestPayloadModel(BaseModel):  # type: ignore[misc]
            run_id: str | None = None
            timeframe: str | None = None
            backtest_start_ts: int | None = None
            backtest_end_ts: int | None = None

            model_config = ConfigDict(extra='allow')

            # Add field validators for better type checking
            @model_validator(mode='before')
            @classmethod
            def validate_timestamps(cls, values: dict[str, Any]) -> dict[str, Any]:
                start_ts = values.get('backtest_start_ts')
                end_ts = values.get('backtest_end_ts')

                # Ensure timestamps are reasonable (Unix timestamps)
                if start_ts is not None and not isinstance(start_ts, (int, float)):
                    raise ValueError('backtest_start_ts must be a number')
                if end_ts is not None and not isinstance(end_ts, (int, float)):
                    raise ValueError('backtest_end_ts must be a number')

                # Ensure start is before end if both are present
                if start_ts is not None and end_ts is not None:
                    if start_ts >= end_ts:
                        raise ValueError('backtest_start_ts must be before backtest_end_ts')

                return values
    else:
        class _BacktestPayloadModel(BaseModel):  # type: ignore[misc]
            run_id: str | None = None
            timeframe: str | None = None
            backtest_start_ts: int | None = None
            backtest_end_ts: int | None = None

            class Config:
                extra = Extra.allow  # type: ignore[attr-defined]

            # Add field validators for better type checking
            @validator('backtest_start_ts', 'backtest_end_ts')
            def validate_timestamps(cls, v: Any, field: ModelField) -> Any:  # type: ignore[name-defined]
                if v is not None and not isinstance(v, (int, float)):
                    raise ValueError(f'{field.name} must be a number')
                return v

    if _PYD_V2:
        class _HyperoptTrialModel(BaseModel):  # type: ignore[misc]
            loss: float | None = None
            params_dict: dict[str, Any] | None = None
            results_metrics: dict[str, Any] | None = None

            model_config = ConfigDict(extra='allow')

            # Add field validators for better type checking
            @model_validator(mode='before')
            @classmethod
            def validate_trial(cls, values: dict[str, Any]) -> dict[str, Any]:
                # Validate loss is a number if present
                loss = values.get('loss')
                if loss is not None and not isinstance(loss, (int, float)):
                    raise ValueError('loss must be a number')

                # Validate params_dict is a dict if present
                params = values.get('params_dict')
                if params is not None and not isinstance(params, dict):
                    raise ValueError('params_dict must be a dictionary')

                # Validate results_metrics is a dict if present
                metrics = values.get('results_metrics')
                if metrics is not None and not isinstance(metrics, dict):
                    raise ValueError('results_metrics must be a dictionary')

                return values
    else:
        class _HyperoptTrialModel(BaseModel):  # type: ignore[misc]
            loss: float | None = None
            params_dict: dict[str, Any] | None = None
            results_metrics: dict[str, Any] | None = None

            class Config:
                extra = Extra.allow  # type: ignore[attr-defined]

            # Add field validators for better type checking
            @validator('loss')
            def validate_loss(cls, v: Any) -> Any:  # type: ignore[name-defined]
                if v is not None and not isinstance(v, (int, float)):
                    raise ValueError('loss must be a number')
                return v

            @validator('params_dict', 'results_metrics')
            def validate_dict_fields(cls, v: Any, field: ModelField) -> Any:  # type: ignore[name-defined]
                if v is not None and not isinstance(v, dict):
                    raise ValueError(f'{field.name} must be a dictionary')
                return v

    _PYDANTIC_OK = True
except Exception:  # pragma: no cover - pydantic not installed
    _PYDANTIC_OK = False
    _BacktestPayloadModel = None  # type: ignore[assignment]
    _HyperoptTrialModel = None  # type: ignore[assignment]


def _validate_backtest_payload(payload: dict[str, Any]) -> tuple[bool, str | None]:
    logger = get_json_logger("metrics", static_fields={"op": "_validate_backtest_payload"})
    """Validate backtest payload with Pydantic if available; otherwise run soft checks."""
    if _PYDANTIC_OK and _BacktestPayloadModel is not None:
        try:
            _BacktestPayloadModel.model_validate(payload)  # type: ignore[attr-defined]
            logger.debug("pydantic_validation_success")
            return True, None
        except Exception as e:  # pragma: no cover - validation error
            logger.debug("pydantic_validation_failed", extra={"error": str(e)})
            return False, str(e)
    # Soft validation
    if not isinstance(payload, dict):
        return False, "payload_not_dict"
    # If present, ensure types are reasonable
    for k in ("backtest_start_ts", "backtest_end_ts"):
        v = payload.get(k)
        if v is not None and not isinstance(v, (int, float)):
            return False, f"{k}_not_number"
    return True, None


def _validate_hyperopt_trial(rec: dict[str, Any]) -> bool:
    logger = get_json_logger("metrics", static_fields={"op": "_validate_hyperopt_trial"})
    if _PYDANTIC_OK and _HyperoptTrialModel is not None:
        try:
            _HyperoptTrialModel.model_validate(rec)  # type: ignore[attr-defined]
            logger.debug("pydantic_validation_success")
            return True
        except Exception as e:  # pragma: no cover
            logger.debug("pydantic_validation_failed", extra={"error": str(e)})
            return False
    # Soft validation
    return isinstance(rec, dict)
