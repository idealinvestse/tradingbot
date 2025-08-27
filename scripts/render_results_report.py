from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.strategies.reporting import generate_results_markdown_from_db


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Render latest results report (Markdown) from the SQLite index."
    )
    p.add_argument(
        "--db",
        type=Path,
        default=Path("user_data/backtest_results/index.db"),
        help="Path to SQLite DB containing runs/metrics (default: user_data/backtest_results/index.db)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("user_data/backtest_results/RESULTS.md"),
        help="Output path for Markdown report (default: user_data/backtest_results/RESULTS.md)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max number of runs to include (default: 50)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path: Path = args.db
    out_path: Path = args.out
    limit: int = args.limit

    if not db_path.exists():
        print(f"[render_results_report] DB not found: {db_path}", file=sys.stderr)
        return 2

    try:
        md = generate_results_markdown_from_db(db_path, limit=limit)
    except Exception as e:  # pragma: no cover - CLI runtime
        print(f"[render_results_report] Failed to generate report: {e}", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"Wrote report -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
