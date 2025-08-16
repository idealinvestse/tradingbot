from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable


# Core schema (registry)
SCHEMA: dict[str, str] = {
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
            refs TEXT
        )
        """
    ),
    "concepts": (
        """
        CREATE TABLE IF NOT EXISTS concepts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            refs TEXT
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

# Extended schema (ideation / experiments)
EXTENDED_SCHEMA: dict[str, str] = {
    "ideas": (
        """
        CREATE TABLE IF NOT EXISTS ideas (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT,
            tags TEXT,
            sources TEXT,
            owner TEXT,
            created_utc TEXT
        )
        """
    ),
    "experiments": (
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            idea_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            hypothesis TEXT,
            timeframe TEXT,
            markets TEXT,
            period_start_utc TEXT,
            period_end_utc TEXT,
            seed INTEGER,
            config_hash TEXT,
            created_utc TEXT
        )
        """
    ),
    "runs": (
        """
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            kind TEXT,
            started_utc TEXT,
            finished_utc TEXT,
            status TEXT,
            docker_image TEXT,
            freqtrade_version TEXT,
            config_json TEXT,
            data_window TEXT,
            artifacts_path TEXT
        )
        """
    ),
    "metrics": (
        """
        CREATE TABLE IF NOT EXISTS metrics (
            run_id TEXT,
            key TEXT,
            value REAL,
            PRIMARY KEY (run_id, key)
        )
        """
    ),
    "artifacts": (
        """
        CREATE TABLE IF NOT EXISTS artifacts (
            run_id TEXT,
            name TEXT,
            path TEXT,
            sha256 TEXT,
            PRIMARY KEY (run_id, name)
        )
        """
    ),
    "decisions": (
        """
        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            idea_id TEXT,
            decision TEXT,
            rationale TEXT,
            decided_utc TEXT,
            approver TEXT
        )
        """
    ),
    "incidents": (
        """
        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            severity TEXT,
            description TEXT,
            log_excerpt_path TEXT,
            created_utc TEXT
        )
        """
    ),
}


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def ensure_schema(conn: sqlite3.Connection, with_extended: bool = True) -> None:
    cur = conn.cursor()
    for sql in SCHEMA.values():
        cur.execute(sql)
    if with_extended:
        for sql in EXTENDED_SCHEMA.values():
            cur.execute(sql)
    conn.commit()


def _csv(values: Iterable[Any] | None) -> str:
    if not values:
        return ""
    return ",".join(str(v) for v in values)


def upsert_registry(conn: sqlite3.Connection, registry: Dict[str, Any]) -> None:
    cur = conn.cursor()

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
                _csv(s.get("timeframes")),
                _csv(s.get("markets")),
                _csv(s.get("indicators")),
                json.dumps(s.get("parameters", {}), ensure_ascii=False),
                json.dumps(s.get("risk", {}), ensure_ascii=False),
                json.dumps(s.get("performance", {}), ensure_ascii=False),
                _csv(s.get("tags")),
            ),
        )

    for m in registry.get("methods", []):
        cur.execute(
            """
            INSERT INTO methods (
                id, name, category, description, related_strategies, refs
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                description=excluded.description,
                related_strategies=excluded.related_strategies,
                refs=excluded.refs
            """,
            (
                m.get("id"),
                m.get("name"),
                m.get("category"),
                m.get("description"),
                _csv(m.get("related_strategies")),
                _csv(m.get("references")),
            ),
        )

    for c in registry.get("concepts", []):
        cur.execute(
            """
            INSERT INTO concepts (
                id, name, description, refs
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                refs=excluded.refs
            """,
            (
                c.get("id"),
                c.get("name"),
                c.get("description"),
                _csv(c.get("references")),
            ),
        )

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
