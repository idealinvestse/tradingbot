from __future__ import annotations

import argparse
from pathlib import Path

from app.strategies.runner import run_live


def _parse_exposures(items: list[str] | None) -> dict[str, float] | None:
    if not items:
        return None
    out: dict[str, float] = {}
    for it in items:
        if "=" not in it:
            continue
        key, raw = it.split("=", 1)
        key = key.strip()
        val = raw.strip().rstrip("%")
        try:
            f = float(val)
        except ValueError:
            continue
        # Accept 0..1 or percent; if originally had '%' or f>1 assume percent and normalize
        if raw.strip().endswith("%") or abs(f) > 1.0:
            f = f / 100.0
        out[key] = f
    return out or None


essential = """
Examples:
  py -3 scripts/run_live.py --config user_data\\configs\\config.mainnet.json --strategy MaCrossoverStrategy \
    --open-trades 3 --exposure BTC/USDT=25% --exposure ETH/USDT=0.15

Notes:
- open-trades is the current count of open trades (int).
- exposure values accept either percentages (e.g., 25%) or fractions (0.25).
"""


def main() -> int:
    p = argparse.ArgumentParser(
        description="Launch freqtrade live with RiskManager guardrails",
        epilog=essential,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--config",
        required=True,
        help="Path to freqtrade config JSON (e.g., user_data/configs/config.mainnet.json)",
    )
    p.add_argument("--strategy", help="Strategy class name (optional, can be in config)")
    p.add_argument(
        "--open-trades", type=int, dest="open_trades", help="Currently open trades count"
    )
    p.add_argument(
        "--exposure",
        action="append",
        help="Per-market exposure e.g. BTC/USDT=25% or ETH/USDT=0.15 (repeatable)",
    )
    p.add_argument("--extra", action="append", help="Extra args passed to freqtrade (repeatable)")
    p.add_argument("--correlation-id", dest="cid", help="Optional correlation id for logs")

    args = p.parse_args()

    exposures = _parse_exposures(args.exposure)
    addl = list(args.extra) if args.extra else None

    res = run_live(
        config_path=Path(args.config),
        strategy=args.strategy,
        addl_args=addl,
        open_trades_count=args.open_trades,
        market_exposure_pct=exposures,
        correlation_id=args.cid,
    )

    # Print process output for convenience
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr)
    return res.returncode


if __name__ == "__main__":
    raise SystemExit(main())
