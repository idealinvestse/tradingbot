import importlib.util
import pathlib

import pytest


def test_strategy_loads():
    strat_path = pathlib.Path("user_data/strategies/ma_crossover_strategy.py").resolve()
    spec = importlib.util.spec_from_file_location("ma_crossover_strategy", strat_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except ModuleNotFoundError as e:
        # Allow local test runs without freqtrade installed; container handles deps.
        if "freqtrade" in str(e):
            pytest.skip("freqtrade not installed locally; skipping strategy import")
        raise
    assert hasattr(module, "MaCrossoverStrategy")
    s = module.MaCrossoverStrategy()
    assert s.timeframe in {"1m", "5m", "15m", "1h", "4h", "1d"}
