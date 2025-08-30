from __future__ import annotations

import argparse
import shlex
import subprocess
import sys

from app.strategies.logging_utils import get_json_logger


def download_data(
    *,
    exchange: str = "binance",
    pairs: list[str] | None = None,
    timeframes: list[str] | None = None,
    days: int = 30,
    include_inactive: bool = False,
) -> int:
    logger = get_json_logger("download-data", static_fields={"component": "download-data"})
    pairs = pairs or ["BTC/USDT", "ETH/USDT"]
    timeframes = timeframes or ["1m", "5m"]

    cmd = [
        "freqtrade",
        "download-data",
        "--exchange",
        exchange,
        "--days",
        str(days),
        "--timeframes",
        *timeframes,
        "--pairs",
        *pairs,
    ]
    if include_inactive:
        cmd.append("--include-inactive")

    logger.info("download_start", extra={"cmd": " ".join(shlex.quote(c) for c in cmd)})
    try:
        proc = subprocess.run(cmd, check=False)
        code = int(proc.returncode)
        if code == 0:
            logger.info("download_success", extra={"exit_code": code})
        else:
            logger.error("download_failed", extra={"exit_code": code})
        return code
    except Exception as e:  # noqa: BLE001
        logger.error("download_exception", extra={"error": str(e)})
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Download historical data via Freqtrade.")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--timeframes", nargs="+", default=["1m", "5m"])
    parser.add_argument("--pairs", nargs="+", default=["BTC/USDT", "ETH/USDT"])
    parser.add_argument("--include-inactive", action="store_true")
    args = parser.parse_args()

    return download_data(
        exchange=args.exchange,
        pairs=args.pairs,
        timeframes=args.timeframes,
        days=args.days,
        include_inactive=args.include_inactive,
    )


if __name__ == "__main__":
    sys.exit(main())
