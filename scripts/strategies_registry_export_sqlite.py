from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


SCHEMA = {
    "strategies": (
        """
        CREATE TABLE IF NOT EXISTS strategies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            class_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            status TEXT,
            timeframes TEXT,
            markets TEXT,
            indicators TEXT,
            parameters_json TEXT,
            risk_json TEXT,
            performance_json TEXT,
            tags TEXT
        )
        """
    ),
    "methods": (
        """
        CREATE TABLE IF NOT EXISTS methods (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            description TEXT,
            related_strategies TEXT,
            references TEXT
        )
        """
    ),
    "concepts": (
        """
        CREATE TABLE IF NOT EXISTS concepts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            references TEXT
        )
        """
    ),
    "sources": (
        """
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            title TEXT,
            path TEXT,
            topic TEXT,
            quality TEXT
        )
        """
    ),
}


def load_registry(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    for sql in SCHEMA.values():
        cur.execute(sql)
    conn.commit()


def _csv(values: List[Any]) -> str:
    if not values:
        return ""
    return ",".join(str(v) for v in values)


def upsert_registry(conn: sqlite3.Connection, registry: Dict[str, Any]) -> None:
    cur = conn.cursor()

    # strategies
    for s in registry.get("strategies", []):
        cur.execute(
            """
            INSERT INTO strategies (
                id, name, class_name, file_path, status, timeframes, markets,
                indicators, parameters_json, risk_json, performance_json, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                class_name=excluded.class_name,
                file_path=excluded.file_path,
                status=excluded.status,
                timeframes=excluded.timeframes,
                markets=excluded.markets,
                indicators=excluded.indicators,
                parameters_json=excluded.parameters_json,
                risk_json=excluded.risk_json,
                performance_json=excluded.performance_json,
                tags=excluded.tags
            """,
            (
                s.get("id"),
                s.get("name"),
                s.get("class_name"),
                s.get("file_path"),
                s.get("status"),
                _csv(s.get("timeframes", [])),
                _csv(s.get("markets", [])),
                _csv(s.get("indicators", [])),
                json.dumps(s.get("parameters", {}), ensure_ascii=False),
                json.dumps(s.get("risk", {}), ensure_ascii=False),
                json.dumps(s.get("performance", {}), ensure_ascii=False),
                _csv(s.get("tags", [])),
            ),
        )

    # methods
    for m in registry.get("methods", []):
        cur.execute(
            """
            INSERT INTO methods (
                id, name, category, description, related_strategies, references
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                description=excluded.description,
                related_strategies=excluded.related_strategies,
                references=excluded.references
            """,
            (
                m.get("id"),
                m.get("name"),
                m.get("category"),
                m.get("description"),
                _csv(m.get("related_strategies", [])),
                _csv(m.get("references", [])),
            ),
        )

    # concepts
    for c in registry.get("concepts", []):
        cur.execute(
            """
            INSERT INTO concepts (
                id, name, description, references
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                references=excluded.references
            """,
            (
                c.get("id"),
                c.get("name"),
                c.get("description"),
                _csv(c.get("references", [])),
            ),
        )

    # sources
    for s in registry.get("sources", []):
        cur.execute(
            """
            INSERT INTO sources (
                id, title, path, topic, quality
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                path=excluded.path,
                topic=excluded.topic,
                quality=excluded.quality
            """,
            (
                s.get("id"),
                s.get("title"),
                s.get("path"),
                s.get("topic"),
                s.get("quality"),
            ),
        )

    conn.commit()


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Exportera docs/strategies_registry.json till SQLite för enkel sökning och versionering."
        )
    )
    default_registry = Path(__file__).resolve().parents[1] / "docs" / "strategies_registry.json"
    default_out_dir = Path(__file__).resolve().parents[1] / "user_data" / "registry"
    ap.add_argument("--registry", default=str(default_registry), help="Sökväg till registry JSON")
    ap.add_argument(
        "--out",
        default=str(default_out_dir / "strategies_registry.sqlite"),
        help="Sökväg till SQLite-databas",
    )
    args = ap.parse_args()

    reg_path = Path(args.registry)
    db_path = Path(args.out)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    registry = load_registry(reg_path)

    conn = sqlite3.connect(db_path)
    try:
        ensure_schema(conn)
        upsert_registry(conn, registry)
    finally:
        conn.close()

    print(f"Wrote {db_path}")


if __name__ == "__main__":
    main()
