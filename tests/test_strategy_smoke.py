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
        # Allow local test runs without freqtrade/pandas installed; container handles deps.
        if ("freqtrade" in str(e)) or ("pandas" in str(e)):
            pytest.skip("dependency missing locally (freqtrade/pandas); skipping strategy import")
        raise
    assert hasattr(module, "MaCrossoverStrategy")
    s = module.MaCrossoverStrategy()
    assert s.timeframe in {"1m", "5m", "15m", "1h", "4h", "1d"}


def test_momentum_macd_rsi_loads():
    strat_path = pathlib.Path("user_data/strategies/momentum_macd_rsi.py").resolve()
    spec = importlib.util.spec_from_file_location("momentum_macd_rsi", strat_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except ModuleNotFoundError as e:
        if ("freqtrade" in str(e)) or ("pandas" in str(e)):
            pytest.skip("dependency missing locally (freqtrade/pandas); skipping strategy import")
        raise
    assert hasattr(module, "MomentumMacdRsiStrategy")
    s = module.MomentumMacdRsiStrategy()
    assert s.timeframe in {"1m", "5m", "15m", "1h", "4h", "1d"}


def test_bb_breakout_loads():
    strat_path = pathlib.Path("user_data/strategies/bb_breakout_strategy.py").resolve()
    spec = importlib.util.spec_from_file_location("bb_breakout_strategy", strat_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except ModuleNotFoundError as e:
        if ("freqtrade" in str(e)) or ("pandas" in str(e)):
            pytest.skip("dependency missing locally (freqtrade/pandas); skipping strategy import")
        raise
    assert hasattr(module, "BollingerBreakoutStrategy")
    s = module.BollingerBreakoutStrategy()
    assert s.timeframe in {"1m", "5m", "15m", "1h", "4h", "1d"}


def test_wma_stoch_swing_loads():
    strat_path = pathlib.Path("user_data/strategies/wma_stoch_strategy.py").resolve()
    spec = importlib.util.spec_from_file_location("wma_stoch_strategy", strat_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except ModuleNotFoundError as e:
        if ("freqtrade" in str(e)) or ("pandas" in str(e)):
            pytest.skip("dependency missing locally (freqtrade/pandas); skipping strategy import")
        raise
    assert hasattr(module, "WmaStochSwingStrategy")
    s = module.WmaStochSwingStrategy()
    assert s.timeframe in {"1m", "5m", "15m", "1h", "4h", "1d"}
