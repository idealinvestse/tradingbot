from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.strategies.logging_utils import get_json_logger

DEFAULT_STATE_DIR = Path("user_data/state")
DEFAULT_CB_FILE = DEFAULT_STATE_DIR / "circuit_breaker.json"


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _to_until_iso(minutes: int | None, until_iso: str | None) -> str | None:
    if until_iso:
        # Validate/normalize
        try:
            s = until_iso.replace("Z", "+00:00")
            ts = datetime.fromisoformat(s)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts.isoformat()
        except Exception:
            raise SystemExit("Invalid --until ISO timestamp")
    if minutes and minutes > 0:
        return (datetime.now(tz=timezone.utc) + timedelta(minutes=minutes)).isoformat()
    return None


def cmd_status(file_path: Path, correlation_id: str) -> int:
    logger = get_json_logger("circuit_breaker", static_fields={"correlation_id": correlation_id})
    if not file_path.exists():
        logger.info("cb_status", extra={"exists": False, "active": False})
        print("Circuit Breaker: inactive (no file)")
        return 0
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("cb_status_error", extra={"error": str(e)})
        print("Circuit Breaker: error reading file")
        return 1
    active = bool(data.get("active"))
    reason = data.get("reason")
    until_iso = data.get("until_iso")
    logger.info(
        "cb_status",
        extra={"exists": True, "active": active, "reason": reason, "until_iso": until_iso},
    )
    print(
        f"Circuit Breaker: {'ACTIVE' if active else 'inactive'} | reason={reason} | until={until_iso}"
    )
    return 0


def cmd_enable(
    file_path: Path, reason: str, minutes: int | None, until_iso: str | None, correlation_id: str
) -> int:
    logger = get_json_logger("circuit_breaker", static_fields={"correlation_id": correlation_id})
    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "active": True,
        "reason": reason,
    }
    ui = _to_until_iso(minutes, until_iso)
    if ui:
        payload["until_iso"] = ui
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "cb_enabled",
        extra={"file": str(file_path), "reason": reason, "until_iso": payload.get("until_iso")},
    )
    print(f"Circuit Breaker enabled. File: {file_path}")
    return 0


def cmd_disable(file_path: Path, correlation_id: str) -> int:
    logger = get_json_logger("circuit_breaker", static_fields={"correlation_id": correlation_id})
    if not file_path.exists():
        logger.info("cb_disable_noop", extra={"file": str(file_path)})
        print("Circuit Breaker already inactive.")
        return 0
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data.update({"active": False})
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("cb_disabled", extra={"file": str(file_path)})
    print("Circuit Breaker disabled.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Circuit Breaker helper")
    parser.add_argument("command", choices=["status", "enable", "disable"], help="Action")
    parser.add_argument(
        "--state-dir",
        dest="state_dir",
        default=str(DEFAULT_STATE_DIR),
        help="State directory (default: user_data/state)",
    )
    parser.add_argument(
        "--file",
        dest="file",
        default=None,
        help="Path to circuit_breaker.json (overrides --state-dir)",
    )
    parser.add_argument("--reason", dest="reason", default="manual", help="Reason for enable")
    parser.add_argument(
        "--minutes", dest="minutes", type=int, default=None, help="Enable duration in minutes"
    )
    parser.add_argument(
        "--until",
        dest="until_iso",
        default=None,
        help="Enable until ISO timestamp (e.g. 2025-08-17T10:15:00Z)",
    )

    args = parser.parse_args()
    cid = uuid.uuid4().hex

    if args.file:
        file_path = Path(args.file)
    else:
        file_path = Path(args.state_dir) / "circuit_breaker.json"

    if args.command == "status":
        return cmd_status(file_path, cid)
    if args.command == "enable":
        return cmd_enable(file_path, args.reason, args.minutes, args.until_iso, cid)
    if args.command == "disable":
        return cmd_disable(file_path, cid)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
