from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG_STD_KEYS = {
    'name','msg','args','levelname','levelno','pathname','filename','module','exc_info','exc_text',
    'stack_info','lineno','funcName','created','msecs','relativeCreated','thread','threadName',
    'processName','process','asctime'
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        now = datetime.now(tz=timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "ts": now,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include any extra fields that are simple JSON types
        for k, v in record.__dict__.items():
            if k in _LOG_STD_KEYS:
                continue
            if k.startswith('_'):
                continue
            # Filter to basic JSON-serializable scalars/containers
            if isinstance(v, (str, int, float, bool)) or v is None:
                payload[k] = v
            elif isinstance(v, (list, dict)):
                # Best-effort: include if JSON serializable
                try:
                    json.dumps(v)
                except Exception:
                    continue
                else:
                    payload[k] = v
        return json.dumps(payload, ensure_ascii=False)


def get_json_logger(
    name: str,
    *,
    log_path: Path | None = None,
    level: int = logging.INFO,
    static_fields: dict[str, Any] | None = None,
) -> logging.LoggerAdapter:
    """Create or fetch a JSON logger with optional file output and static fields.

    Returns a LoggerAdapter that injects `static_fields` into each record.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers: add only if empty
    if not logger.handlers:
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handler: logging.Handler = logging.FileHandler(log_path, encoding='utf-8')
        else:
            handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False  # stay self-contained

    adapter = logging.LoggerAdapter(logger, extra=static_fields or {})
    return adapter


def get_context_logger(
    name: str,
    context: dict[str, Any] | None = None,
    *,
    log_path: Path | None = None,
    level: int = logging.INFO,
) -> logging.LoggerAdapter:
    """Convenience wrapper to obtain a JSON logger with contextual fields.

    Example:
        logger = get_context_logger("risk", {"correlation_id": cid, "run_id": run_id})
    """
    return get_json_logger(name, log_path=log_path, level=level, static_fields=context)
