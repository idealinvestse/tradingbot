from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List


@dataclass
class DcaOrder:
    at: datetime
    pair: str
    amount: float  # in stake currency (USDT)


@dataclass
class DcaPlan:
    orders: List[DcaOrder]


def build_dca_plan(start: datetime, end: datetime, interval: str, pair: str, amount: float) -> DcaPlan:
    delta_map = {
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "biweekly": timedelta(days=14),
        "monthly": timedelta(days=30),  # approximated for simplicity
    }
    if interval not in delta_map:
        raise ValueError(f"Unsupported interval: {interval}")

    orders: List[DcaOrder] = []
    t = start
    step = delta_map[interval]
    while t <= end:
        orders.append(DcaOrder(at=t, pair=pair, amount=amount))
        t += step
    return DcaPlan(orders=orders)


def save_plan_csv(plan: DcaPlan, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["at_utc", "pair", "amount"])
        for o in plan.orders:
            w.writerow([o.at.replace(tzinfo=timezone.utc).isoformat(), o.pair, f"{o.amount:.2f}"])


def main() -> None:
    p = argparse.ArgumentParser(description="DCA scheduler: generates a CSV buy plan from a JSON config.")
    p.add_argument("--config", required=True, help="Path to DCA config JSON")
    p.add_argument("--out", required=True, help="Path to output CSV plan")
    args = p.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    start = datetime.fromisoformat(cfg["start_utc"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(cfg["end_utc"].replace("Z", "+00:00"))
    interval = cfg["interval"]  # daily|weekly|biweekly|monthly
    pair = cfg["pair"]
    amount = float(cfg["amount_usdt"])  # stake currency

    plan = build_dca_plan(start, end, interval, pair, amount)
    save_plan_csv(plan, Path(args.out))


if __name__ == "__main__":
    main()
