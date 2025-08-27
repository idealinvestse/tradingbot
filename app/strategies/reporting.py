from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .logging_utils import get_json_logger


def _csv(values: list[Any] | None, dash: str = "-") -> str:
    if not values:
        return dash
    return ", ".join(str(v) for v in values)


def _safe(d: dict[str, Any], key: str, default: Any = "-") -> Any:
    v = d.get(key)
    return v if v not in (None, "") else default


def generate_markdown(registry: dict[str, Any]) -> str:
    """Build Markdown overview from registry dict.

    Uses UTC for timestamp if registry lacks updated_utc.
    """
    cid = uuid.uuid4().hex
    logger = get_json_logger("reporting", static_fields={"correlation_id": cid, "op": "generate_markdown"})
    logger.info("start", extra={"strategy_count": len(registry.get("strategies", []))})
    updated = registry.get("updated_utc") or datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: list[str] = []
    lines.append("# Strategier, metoder och koncept – Registry")
    lines.append("")
    lines.append(f"Senast uppdaterad (UTC): {updated}")
    lines.append("")

    # Strategies table
    lines.append("## Strategier")
    lines.append("")
    lines.append("| ID | Namn | Klass | Fil | Status | Timeframes | Marknader | Indikatorer | Taggar |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for s in registry.get("strategies", []):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(_safe(s, "id")),
                    str(_safe(s, "name")),
                    str(_safe(s, "class_name")),
                    str(_safe(s, "file_path")),
                    str(_safe(s, "status")),
                    _csv(s.get("timeframes")),
                    _csv(s.get("markets")),
                    _csv(s.get("indicators")),
                    _csv(s.get("tags")),
                ]
            )
            + " |"
        )
    lines.append("")

    # Methods table
    lines.append("## Metoder")
    lines.append("")
    lines.append("| ID | Namn | Kategori | Beskrivning | Relaterade strategier | Referenser |")
    lines.append("|---|---|---|---|---|---|")
    for m in registry.get("methods", []):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(_safe(m, "id")),
                    str(_safe(m, "name")),
                    str(_safe(m, "category")),
                    str(_safe(m, "description")),
                    _csv(m.get("related_strategies")),
                    _csv(m.get("references")),
                ]
            )
            + " |"
        )
    lines.append("")

    # Concepts table
    lines.append("## Koncept")
    lines.append("")
    lines.append("| ID | Namn | Beskrivning | Referenser |")
    lines.append("|---|---|---|---|")
    for c in registry.get("concepts", []):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(_safe(c, "id")),
                    str(_safe(c, "name")),
                    str(_safe(c, "description")),
                    _csv(c.get("references")),
                ]
            )
            + " |"
        )
    lines.append("")

    # Sources table
    lines.append("## Källor")
    lines.append("")
    lines.append("| ID | Titel | Plats | Ämne | Kvalitet |")
    lines.append("|---|---|---|---|---|")
    for s in registry.get("sources", []):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(_safe(s, "id")),
                    str(_safe(s, "title")),
                    str(_safe(s, "path")),
                    str(_safe(s, "topic")),
                    str(_safe(s, "quality")),
                ]
            )
            + " |"
        )
    lines.append("")

    out = "\n".join(lines) + "\n"
    logger.info("done", extra={"lines_generated": len(lines), "output_bytes": len(out)}) # Added output_bytes
    return out


def generate_results_markdown_from_db(db_path: Path, limit: int = 20) -> str:
    """Generate a Markdown report of recent runs with key metrics from SQLite DB.

    Shows latest runs ordered by finished_utc (desc) with selected metrics.
    """
    cid = uuid.uuid4().hex
    logger = get_json_logger("reporting", static_fields={"correlation_id": cid, "op": "results_report"})
    logger.info("start", extra={"db_path": str(db_path), "limit": limit})
    keys = [
        "profit_total",
        "profit_total_abs",
        "sharpe",
        "sortino",
        "max_drawdown_abs",
        "winrate",
        "loss",
        "trades",
    ]
    logger.debug("metric_keys_to_report", extra={"keys": keys})

    def _mmap(cur: sqlite3.Cursor, run_id: str) -> dict[str, float]:
        cur.execute(
            "SELECT key, value FROM metrics WHERE run_id = ?",
            (run_id,),
        )
        # Use Decimal for monetary values to maintain precision when displaying
        # Only convert to float for display purposes
        result = {}
        for k, v in cur.fetchall():
            # For monetary values, use Decimal for better precision
            monetary_keys = ('profit_total', 'profit_total_abs', 'max_drawdown_abs')
            if k in monetary_keys:
                decimal_v = Decimal(str(v)).quantize(Decimal('0.00000001'))
                result[k] = float(decimal_v)
            else:
                result[k] = float(v)
        return result

    logger.debug("connecting_db", extra={"db_path": str(db_path)})
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = con.cursor()
    except sqlite3.OperationalError as e:
        logger.error("db_connect_failed", extra={"db_path": str(db_path), "error": str(e)})
        return f"# Fel: Kunde inte ansluta till databasen\n\nKunde inte öppna: `{db_path}`. Kontrollera att filen existerar och har korrekta läsbehörigheter."

    # Detect optional columns/tables for backward compatibility
    cur.execute("PRAGMA table_info(runs)")
    run_cols = {r[1] for r in cur.fetchall()}  # type: ignore[index]
    cur.execute("PRAGMA table_info(experiments)")
    exp_cols = {r[1] for r in cur.fetchall()}  # type: ignore[index]
    logger.debug("db_schema_info", extra={"run_columns": list(run_cols), "experiment_columns": list(exp_cols)})

    # Always select the core columns; we'll fetch optional fields per-row later
    cur.execute(
        "SELECT id, experiment_id, kind, started_utc, finished_utc, status FROM runs ORDER BY finished_utc DESC LIMIT ?",
        (limit,),
    )
    rows: list[tuple[str, str, str, str, str, str]] = cur.fetchall()
    logger.info("runs_fetched", extra={"count": len(rows)})
    con.close()

    now_utc = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = []
    lines.append("# Resultat – senaste körningar")
    lines.append("")
    lines.append(f"Genererad (UTC): {now_utc}")
    lines.append("")

    if not rows:
        lines.append("Inga körningar hittades.")
        out = "\n".join(lines) + "\n"
        logger.info("done", extra={"rows": 0})
        return out

    # Table header (include Data Window and Config Hash)
    lines.append(
        "| Run ID | Status | Start | Slut | Typ | Data Window | Config Hash | profit_total | profit_total_abs | sharpe | sortino | max_dd_abs | winrate | loss | trades |"
    )
    lines.append("|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    # Re-compute presence flags in this connection
    cur.execute("PRAGMA table_info(runs)")
    run_cols = {r[1] for r in cur.fetchall()}  # type: ignore[index]
    cur.execute("PRAGMA table_info(experiments)")
    exp_cols = {r[1] for r in cur.fetchall()}  # type: ignore[index]
    logger.debug("db_schema_info", extra={"run_columns": list(run_cols), "experiment_columns": list(exp_cols)})
    for rid, exp, kind, started, finished, status in rows:
        mmap = _mmap(cur, rid)
        vals = [mmap.get(k, None) for k in keys]
        fmt = lambda x: (f"{x:.8f}" if isinstance(x, (int, float)) else "-")
        # Optional fields with graceful fallback
        data_window = "-"
        if "data_window" in run_cols:
            try:
                cur.execute("SELECT data_window FROM runs WHERE id = ?", (rid,))
                dw_row = cur.fetchone()
                if dw_row and dw_row[0]:
                    data_window = str(dw_row[0])
                    logger.debug("found_data_window", extra={"run_id": rid, "data_window": data_window})
            except Exception as e:
                logger.warning("data_window_fetch_failed", extra={"run_id": rid, "error": str(e)})
                data_window = "-"

        config_hash = "-"
        if "config_hash" in exp_cols:
            try:
                cur.execute("SELECT config_hash FROM experiments WHERE id = ?", (exp,))
                ch_row = cur.fetchone()
                if ch_row and ch_row[0]:
                    config_hash = str(ch_row[0])
                    logger.debug("found_config_hash", extra={"run_id": rid, "experiment_id": exp, "config_hash": config_hash})
            except Exception as e:
                logger.warning("config_hash_fetch_failed", extra={"run_id": rid, "experiment_id": exp, "error": str(e)})
                config_hash = "-"
        lines.append(
            "| "
            + " | ".join(
                [
                    rid,
                    status or "-",
                    started or "-",
                    finished or "-",
                    kind or "-",
                    data_window,
                    config_hash,
                    *[fmt(v) for v in vals],
                ]
            )
            + " |"
        )
    con.close()
    logger.debug("db_connection_closed")

    lines.append("")
    lines.append(f"Nycklar: {', '.join(keys)}")
    lines.append("")
    out = "\n".join(lines) + "\n"
    logger.info("done", extra={"lines_generated": len(lines), "output_bytes": len(out)})
    return out
