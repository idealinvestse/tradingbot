from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .logging_utils import get_json_logger
from .persistence.sqlite import connect, ensure_schema, upsert_registry
from .registry_models import RegistrySchema
from .reporting import generate_markdown


def load_registry(path: Path) -> dict[str, Any]:
    """Load registry JSON from path with Pydantic validation.

    Raises FileNotFoundError if missing, JSONDecodeError on invalid JSON.
    Raises ValidationError if registry structure is invalid.
    """
    cid = uuid.uuid4().hex
    logger = get_json_logger(
        "registry", static_fields={"correlation_id": cid, "op": "load_registry"}
    )
    logger.info("start", extra={"path": str(path)})

    data = json.loads(path.read_text(encoding="utf-8"))

    # Validate using Pydantic model
    validated_registry = RegistrySchema(**data)

    logger.info("done", extra={"strategies": len(validated_registry.strategies)})
    return data


def write_markdown(registry: dict[str, Any], out_path: Path) -> None:
    md = generate_markdown(registry)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")


def export_sqlite(registry: dict[str, Any], db_path: Path) -> None:
    cid = uuid.uuid4().hex
    logger = get_json_logger(
        "registry", static_fields={"correlation_id": cid, "op": "export_sqlite"}
    )
    logger.info("start", extra={"db_path": str(db_path)})

    conn = connect(db_path)
    try:
        ensure_schema(conn, with_extended=True)
        upsert_registry(conn, registry)
        logger.info("done")
    finally:
        conn.close()
