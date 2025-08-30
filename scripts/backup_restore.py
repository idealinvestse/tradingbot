from __future__ import annotations

import argparse
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root on sys.path when invoked directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.strategies.logging_utils import get_json_logger


def _utc_now_slug() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")


def backup(
    *,
    out_dir: Path,
    include_backtests: bool,
    include_hyperopts: bool,
    include_registry: bool,
    include_logs: bool,
    correlation_id: str | None = None,
) -> Path:
    cid = correlation_id or uuid.uuid4().hex
    logger = get_json_logger("backup", static_fields={"correlation_id": cid, "op": "backup"})

    user_data = ROOT / "user_data"
    reg_db = user_data / "registry" / "strategies_registry.sqlite"
    back_dir = user_data / "backtest_results"
    hop_dir = user_data / "hyperopt_results"
    logs_dir = user_data / "logs"

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"backup_{_utc_now_slug()}"
    dest.mkdir(parents=True, exist_ok=True)

    logger.info("start", extra={"dest": str(dest)})

    if include_registry and reg_db.exists():
        (dest / "registry").mkdir(exist_ok=True)
        shutil.copy2(reg_db, dest / "registry" / reg_db.name)
        logger.info("copied_registry", extra={"path": str(reg_db)})

    if include_backtests and back_dir.exists():
        # zip folder for compactness
        archive_path = shutil.make_archive(str(dest / "backtest_results"), "zip", str(back_dir))
        logger.info("archived_backtests", extra={"archive": archive_path})

    if include_hyperopts and hop_dir.exists():
        archive_path = shutil.make_archive(str(dest / "hyperopt_results"), "zip", str(hop_dir))
        logger.info("archived_hyperopts", extra={"archive": archive_path})

    if include_logs and logs_dir.exists():
        archive_path = shutil.make_archive(str(dest / "logs"), "zip", str(logs_dir))
        logger.info("archived_logs", extra={"archive": archive_path})

    logger.info("done", extra={"dest": str(dest)})
    return dest


def restore(
    *,
    src_backup: Path,
    restore_backtests: bool,
    restore_hyperopts: bool,
    restore_registry: bool,
    restore_logs: bool,
    overwrite: bool,
    correlation_id: str | None = None,
) -> None:
    cid = correlation_id or uuid.uuid4().hex
    logger = get_json_logger("backup", static_fields={"correlation_id": cid, "op": "restore"})

    user_data = ROOT / "user_data"
    reg_db = user_data / "registry" / "strategies_registry.sqlite"
    back_dir = user_data / "backtest_results"
    hop_dir = user_data / "hyperopt_results"
    logs_dir = user_data / "logs"

    logger.info("start", extra={"src": str(src_backup)})

    if restore_registry:
        src = src_backup / "registry" / "strategies_registry.sqlite"
        if src.exists():
            reg_db.parent.mkdir(parents=True, exist_ok=True)
            if reg_db.exists() and not overwrite:
                logger.warning("registry_exists_skip", extra={"path": str(reg_db)})
            else:
                shutil.copy2(src, reg_db)
                logger.info("restored_registry", extra={"to": str(reg_db)})

    if restore_backtests:
        src_zip = src_backup / "backtest_results.zip"
        if src_zip.exists():
            back_dir.mkdir(parents=True, exist_ok=True)
            shutil.unpack_archive(str(src_zip), extract_dir=str(back_dir), format="zip")
            logger.info("restored_backtests", extra={"to": str(back_dir)})

    if restore_hyperopts:
        src_zip = src_backup / "hyperopt_results.zip"
        if src_zip.exists():
            hop_dir.mkdir(parents=True, exist_ok=True)
            shutil.unpack_archive(str(src_zip), extract_dir=str(hop_dir), format="zip")
            logger.info("restored_hyperopts", extra={"to": str(hop_dir)})

    if restore_logs:
        src_zip = src_backup / "logs.zip"
        if src_zip.exists():
            logs_dir.mkdir(parents=True, exist_ok=True)
            shutil.unpack_archive(str(src_zip), extract_dir=str(logs_dir), format="zip")
            logger.info("restored_logs", extra={"to": str(logs_dir)})

    logger.info("done", extra={"src": str(src_backup)})


def main() -> None:
    ap = argparse.ArgumentParser(description="Backup/restore user_data artifacts")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("backup", help="Create a timestamped backup under user_data/backups/")
    p_b.add_argument(
        "--out",
        default=str(ROOT / "user_data" / "backups"),
        help="Output directory for backups (default: user_data/backups)",
    )
    p_b.add_argument("--no-backtests", action="store_true")
    p_b.add_argument("--no-hyperopts", action="store_true")
    p_b.add_argument("--no-registry", action="store_true")
    p_b.add_argument("--logs", action="store_true", help="Include zipped logs in backup")

    p_r = sub.add_parser("restore", help="Restore from a given backup directory")
    p_r.add_argument(
        "src", help="Path to a backup directory (e.g., user_data/backups/backup_YYYYmmdd_HHMMSS)"
    )
    p_r.add_argument(
        "--only", choices=["registry", "backtests", "hyperopts", "logs"], nargs="*", default=[]
    )
    p_r.add_argument("--overwrite", action="store_true", help="Overwrite existing files if present")

    args = ap.parse_args()

    if args.cmd == "backup":
        dest = backup(
            out_dir=Path(args.out),
            include_backtests=not args.no_backtests,
            include_hyperopts=not args.no_hyperopts,
            include_registry=not args.no_registry,
            include_logs=bool(args.logs),
        )
        print(str(dest))
        return

    if args.cmd == "restore":
        only: set[str] = set(args.only)
        restore(
            src_backup=Path(args.src),
            restore_backtests=(not only or "backtests" in only),
            restore_hyperopts=(not only or "hyperopts" in only),
            restore_registry=(not only or "registry" in only),
            restore_logs=(not only or "logs" in only),
            overwrite=bool(args.overwrite),
        )
        print("OK")
        return


if __name__ == "__main__":
    main()
