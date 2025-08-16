from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure project root is on sys.path so 'app' package resolves when running this script directly
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]

_ROOT = project_root()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.strategies.registry import export_sqlite, load_registry, write_markdown
from app.strategies.introspect import discover_strategies, to_json_dict
from app.strategies.metrics import index_backtests


def main() -> None:
    ap = argparse.ArgumentParser(description="Strategy module CLI – docs sync and DB export")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_docs = sub.add_parser("docs", help="Generate docs/STRATEGIES.md from registry JSON")
    p_docs.add_argument(
        "--registry",
        default=str(project_root() / "docs" / "strategies_registry.json"),
    )

    p_idx = sub.add_parser("index-backtests", help="Parse backtest meta and index into SQLite DB")
    p_idx.add_argument(
        "--dir",
        default=str(project_root() / "user_data" / "backtest_results"),
        help="Directory with *.meta.json files",
    )
    p_idx.add_argument(
        "--db-out",
        default=str(project_root() / "user_data" / "registry" / "strategies_registry.sqlite"),
        help="SQLite DB path",
    )
    p_docs.add_argument(
        "--out",
        default=str(project_root() / "docs" / "STRATEGIES.md"),
    )

    p_db = sub.add_parser("export-db", help="Export registry JSON to SQLite DB")
    p_db.add_argument(
        "--registry",
        default=str(project_root() / "docs" / "strategies_registry.json"),
    )
    p_db.add_argument(
        "--out",
        default=str(project_root() / "user_data" / "registry" / "strategies_registry.sqlite"),
    )

    p_all = sub.add_parser("all", help="Run docs and DB export")
    p_all.add_argument(
        "--registry",
        default=str(project_root() / "docs" / "strategies_registry.json"),
    )
    p_all.add_argument(
        "--md-out",
        default=str(project_root() / "docs" / "STRATEGIES.md"),
    )
    p_all.add_argument(
        "--db-out",
        default=str(project_root() / "user_data" / "registry" / "strategies_registry.sqlite"),
    )

    p_int = sub.add_parser("introspect", help="Scan user_data/strategies and output JSON summary")
    p_int.add_argument(
        "--dir",
        default=str(project_root() / "user_data" / "strategies"),
        help="Directory containing strategy .py files",
    )
    p_int.add_argument(
        "--out",
        default=str(project_root() / "docs" / "strategies_introspection.json"),
        help="Output JSON path",
    )

    args = ap.parse_args()

    if args.cmd == "docs":
        reg = load_registry(Path(args.registry))
        write_markdown(reg, Path(args.out))
        print(f"Wrote {args.out}")
        return

    if args.cmd == "export-db":
        reg = load_registry(Path(args.registry))
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        export_sqlite(reg, out)
        print(f"Wrote {out}")
        return

    if args.cmd == "index-backtests":
        back_dir = Path(args.dir)
        db_out = Path(args.db_out)
        db_out.parent.mkdir(parents=True, exist_ok=True)
        n = index_backtests(back_dir, db_out)
        print(f"Indexed {n} backtest runs into {db_out}")
        return

    if args.cmd == "all":
        reg = load_registry(Path(args.registry))
        md_out = Path(args.md_out)
        db_out = Path(args.db_out)
        md_out.parent.mkdir(parents=True, exist_ok=True)
        db_out.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(reg, md_out)
        export_sqlite(reg, db_out)
        print(f"Wrote {md_out} and {db_out}")
        return

    if args.cmd == "introspect":
        base = Path(args.dir)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        items = discover_strategies(base)
        payload = to_json_dict(items)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {out}")
        return


if __name__ == "__main__":
    main()
