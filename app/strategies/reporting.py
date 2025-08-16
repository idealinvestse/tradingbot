from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


def _csv(values: List[Any] | None, dash: str = "-") -> str:
    if not values:
        return dash
    return ", ".join(str(v) for v in values)


def _safe(d: Dict[str, Any], key: str, default: Any = "-") -> Any:
    v = d.get(key)
    return v if v not in (None, "") else default


def generate_markdown(registry: Dict[str, Any]) -> str:
    """Build Markdown overview from registry dict.

    Uses UTC for timestamp if registry lacks updated_utc.
    """
    updated = registry.get("updated_utc") or datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: List[str] = []
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

    return "\n".join(lines) + "\n"


def generate_results_markdown_from_db(db_path: Path, limit: int = 20) -> str:
    """Generate a Markdown report of recent runs with key metrics from SQLite DB.

    Shows latest runs ordered by finished_utc (desc) with selected metrics.
    """
    keys = [
        "profit_total",
        "profit_total_abs",
        "sharpe",
        "sortino",
        "max_drawdown_abs",
        "winrate",
        "trades",
    ]

    def _mmap(cur: sqlite3.Cursor, run_id: str) -> Dict[str, float]:
        cur.execute(
            "SELECT key, value FROM metrics WHERE run_id = ?",
            (run_id,),
        )
        return {k: float(v) for k, v in cur.fetchall()}

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "SELECT id, experiment_id, kind, started_utc, finished_utc, status FROM runs ORDER BY finished_utc DESC LIMIT ?",
        (limit,),
    )
    rows: List[Tuple[str, str, str, str, str, str]] = cur.fetchall()
    con.close()

    now_utc = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: List[str] = []
    lines.append("# Resultat – senaste körningar")
    lines.append("")
    lines.append(f"Genererad (UTC): {now_utc}")
    lines.append("")

    if not rows:
        lines.append("Inga körningar hittades.")
        return "\n".join(lines) + "\n"

    # Table header
    lines.append(
        "| Run ID | Status | Start | Slut | Typ | profit_total | profit_total_abs | sharpe | sortino | max_dd_abs | winrate | trades |"
    )
    lines.append("|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|")

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    for rid, exp, kind, started, finished, status in rows:
        mmap = _mmap(cur, rid)
        vals = [mmap.get(k, None) for k in keys]
        fmt = lambda x: (f"{x:.6g}" if isinstance(x, (int, float)) else "-")
        lines.append(
            "| "
            + " | ".join(
                [
                    rid,
                    status or "-",
                    started or "-",
                    finished or "-",
                    kind or "-",
                    *[fmt(v) for v in vals],
                ]
            )
            + " |"
        )
    con.close()

    lines.append("")
    lines.append(f"Nycklar: {', '.join(keys)}")
    lines.append("")
    return "\n".join(lines) + "\n"
