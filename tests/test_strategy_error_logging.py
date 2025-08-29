from __future__ import annotations

import io
import json
import logging
from typing import Any, Dict

import pandas as pd
import pytest


def _make_stream_adapter(stream: io.StringIO, static_fields: Dict[str, Any] | None = None):
    logger = logging.getLogger("strategy-test")
    logger.setLevel(logging.INFO)
    # fresh handler for each test
    for h in list(logger.handlers):
        logger.removeHandler(h)
    from app.strategies.logging_utils import JsonFormatter

    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False
    from logging import LoggerAdapter

    return LoggerAdapter(logger, extra=static_fields or {})


@pytest.mark.parametrize(
    "module_name,class_name",
    [
        ("user_data.strategies.ma_crossover_strategy", "MaCrossoverStrategy"),
        ("user_data.strategies.momentum_macd_rsi", "MomentumMacdRsiStrategy"),
    ],
)
def test_dp_ticker_error_logged(monkeypatch, module_name: str, class_name: str):
    stream = io.StringIO()
    # Ensure correlation id is present
    monkeypatch.setenv("CORRELATION_ID", "cid-123")

    # Patch get_json_logger IN strategy module namespace (import-time binding)
    mod = __import__(module_name, fromlist=[class_name, "get_json_logger"])

    def fake_get_json_logger(name: str, **kwargs):  # noqa: ANN001
        static_fields = dict(kwargs.get("static_fields") or {})
        static_fields.setdefault("correlation_id", "cid-123")
        return _make_stream_adapter(stream, static_fields)

    monkeypatch.setattr(mod, "get_json_logger", fake_get_json_logger, raising=True)

    StrategyCls = getattr(mod, class_name)
    strat = StrategyCls()

    class _RunMode:
        value = "dry_run"

    class _DP:
        runmode = _RunMode()

        @staticmethod
        def ticker(pair):  # noqa: ANN001
            raise RuntimeError("rate limit")

    strat.dp = _DP()

    # Minimal OHLCV frame
    df = pd.DataFrame(
        {
            "open": [1, 2, 3, 4, 5],
            "high": [2, 3, 4, 5, 6],
            "low": [0, 1, 2, 3, 4],
            "close": [1.5, 2.5, 3.5, 4.5, 5.5],
            "volume": [10, 10, 10, 10, 10],
        }
    )

    out = strat.populate_indicators(df, {"pair": "BTC/USDT"})
    assert "last_price" in out.columns

    # Validate JSON lines contain our error event
    lines = [l for l in stream.getvalue().splitlines() if l.strip()]
    assert any(json.loads(l)["message"] == "dp_ticker_error" for l in lines)
    sample = json.loads(lines[-1])
    # Fields flattened by LoggerAdapter
    assert sample.get("strategy") == StrategyCls.__name__
    assert sample.get("pair") == "BTC/USDT"
    assert sample.get("runmode") == "dry_run"
    assert sample.get("correlation_id") == "cid-123"
    assert "error" in sample
