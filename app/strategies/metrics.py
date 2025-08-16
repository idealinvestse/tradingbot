from __future__ import annotations

import hashlib
import json
import zipfile
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from .persistence.sqlite import connect, ensure_schema

UTC = timezone.utc


@dataclass
class BacktestMeta:
    strategy_class: str
    run_id: str
    timeframe: Optional[str]
    start_ts: Optional[int]
    end_ts: Optional[int]

    @property
    def start_iso(self) -> Optional[str]:
        if self.start_ts is None:
            return None
        return datetime.fromtimestamp(self.start_ts, tz=UTC).isoformat()

    @property
    def end_iso(self) -> Optional[str]:
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


def parse_backtest_meta(meta_path: Path) -> Optional[BacktestMeta]:
    try:
        data = json.loads(meta_path.read_text(encoding='utf-8'))
    except Exception:
        return None

    if not isinstance(data, dict) or not data:
        return None

    # Structure observed: {"ClassName": { ... entries ... }}
    strat_class = next(iter(data.keys()))
    payload = data[strat_class]

    return BacktestMeta(
        strategy_class=str(strat_class),
        run_id=str(payload.get('run_id')) if payload.get('run_id') else meta_path.stem,
        timeframe=payload.get('timeframe'),
        start_ts=payload.get('backtest_start_ts'),
        end_ts=payload.get('backtest_end_ts'),
    )


def _upsert_experiment(cur, exp_id: str, idea_id: str, strategy_id: str, timeframe: Optional[str], start_iso: Optional[str], end_iso: Optional[str]) -> None:
    cur.execute(
        """
        INSERT INTO experiments (
            id, idea_id, strategy_id, hypothesis, timeframe, markets, period_start_utc, period_end_utc, seed, config_hash, created_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            timeframe=excluded.timeframe,
            period_start_utc=excluded.period_start_utc,
            period_end_utc=excluded.period_end_utc
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
        ),
    )


def _upsert_run(cur, run_id: str, experiment_id: str, kind: str, started_iso: Optional[str], finished_iso: Optional[str], status: str, artifacts_path: Optional[str]) -> None:
    cur.execute(
        """
        INSERT INTO runs (
            id, experiment_id, kind, started_utc, finished_utc, status, docker_image, freqtrade_version, config_json, data_window, artifacts_path
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?)
        ON CONFLICT(id) DO UPDATE SET
            experiment_id=excluded.experiment_id,
            kind=excluded.kind,
            started_utc=excluded.started_utc,
            finished_utc=excluded.finished_utc,
            status=excluded.status,
            artifacts_path=excluded.artifacts_path
        """,
        (
            run_id,
            experiment_id,
            kind,
            started_iso or "",
            finished_iso or "",
            status,
            artifacts_path,
        ),
    )


def _upsert_metric(cur, run_id: str, key: str, value: float) -> None:
    cur.execute(
        """
        INSERT INTO metrics (run_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT(run_id, key) DO UPDATE SET
            value=excluded.value
        """,
        (run_id, key, float(value)),
    )


def _upsert_artifact(cur, run_id: str, name: str, path: str, sha256: Optional[str]) -> None:
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


def _parse_zip_metrics(zip_path: Path) -> Dict[str, float]:
    """Extract key metrics from a Freqtrade backtest ZIP.

    Looks for the main summary JSON inside the ZIP (excludes *_config.json and *_Strategy.json).
    Returns a flat dict of metric_name -> float.
    """
    out: Dict[str, float] = {}
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
                    for k in (
                        'profit_total', 'profit_total_abs', 'profit_mean', 'profit_median',
                        'cagr', 'expectancy', 'expectancy_ratio', 'sortino', 'sharpe', 'calmar',
                        'sqn', 'profit_factor', 'trades_per_day', 'market_change',
                    ):
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
                    for k in (
                        'wins', 'losses', 'draws', 'winrate', 'profit_total', 'profit_total_abs',
                        'profit_mean', 'profit_total_pct', 'duration_avg', 'sortino', 'sharpe',
                        'calmar', 'sqn', 'profit_factor', 'max_drawdown_account', 'max_drawdown_abs',
                        'trades',
                    ):
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
    conn = connect(db_path)
    ensure_schema(conn, with_extended=True)
    cur = conn.cursor()

    count = 0
    for meta_path in sorted(backtests_dir.glob("*.meta.json")):
        meta = parse_backtest_meta(meta_path)
        if not meta:
            continue

        # Create synthetic IDs to tie together minimal experiment/run lineage
        strategy_id = meta.strategy_class  # if registry uses IDs differently, this is a placeholder
        exp_id = f"exp:{strategy_id}:{meta.timeframe or ''}:{meta.start_ts or ''}-{meta.end_ts or ''}"
        _upsert_experiment(cur, exp_id, idea_id=f"idea:auto:{strategy_id}", strategy_id=strategy_id,
                           timeframe=meta.timeframe, start_iso=meta.start_iso, end_iso=meta.end_iso)

        # Run record
        artifacts_dir = str(meta_path.parent)
        _upsert_run(cur, meta.run_id, experiment_id=exp_id, kind="backtest",
                    started_iso=meta.start_iso, finished_iso=meta.end_iso,
                    status="completed", artifacts_path=artifacts_dir)

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

        count += 1

    conn.commit()
    conn.close()
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
    conn = connect(db_path)
    ensure_schema(conn, with_extended=True)
    cur = conn.cursor()

    ts_re = re.compile(r"_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})\\.fthypt$")

    count = 0
    for f in sorted(hyperopt_dir.glob("*.fthypt")):
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
                    try:
                        rec = json.loads(line)
                    except Exception:
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

                    count += 1
        except Exception:
            # best-effort parsing per file
            continue

    conn.commit()
    conn.close()
    return count
