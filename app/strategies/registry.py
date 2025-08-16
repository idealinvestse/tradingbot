from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .reporting import generate_markdown
from .persistence.sqlite import connect, ensure_schema, upsert_registry


def load_registry(path: Path) -> Dict[str, Any]:
    """Load registry JSON from path.

    Raises FileNotFoundError if missing, JSONDecodeError on invalid JSON.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown(registry: Dict[str, Any], out_path: Path) -> None:
    md = generate_markdown(registry)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")


def export_sqlite(registry: Dict[str, Any], db_path: Path) -> None:
    conn = connect(db_path)
    try:
        ensure_schema(conn, with_extended=True)
        upsert_registry(conn, registry)
    finally:
        conn.close()
