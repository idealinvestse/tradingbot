import importlib.util
import pathlib

import pytest


def _load_module(path: str, name: str):
    strat_path = pathlib.Path(path).resolve()
    spec = importlib.util.spec_from_file_location(name, strat_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except ModuleNotFoundError as e:
        # Allow local test runs without freqtrade/pandas installed; container handles deps.
        if ("freqtrade" in str(e)) or ("pandas" in str(e)):
            pytest.skip("dependency missing locally (freqtrade/pandas); skipping strategy import")
        raise
    return module


def test_mean_reversion_bb_loads():
    module = _load_module("user_data/strategies/mean_reversion_bb.py", "mean_reversion_bb")
    assert hasattr(module, "MeanReversionBbStrategy")
    config = {"dry_run": True, "stake_currency": "USDT"}
    s = module.MeanReversionBbStrategy(config)
    assert s.timeframe in {"1m", "5m", "15m", "1h", "4h", "1d"}


def test_breakout_bb_vol_loads():
    module = _load_module("user_data/strategies/breakout_bb_vol.py", "breakout_bb_vol")
    assert hasattr(module, "BreakoutBbVolStrategy")
    config = {"dry_run": True, "stake_currency": "USDT"}
    s = module.BreakoutBbVolStrategy(config)
    assert s.timeframe in {"1m", "5m", "15m", "1h", "4h", "1d"}


def test_hodl_loads():
    module = _load_module("user_data/strategies/hodl_strategy.py", "hodl_strategy")
    assert hasattr(module, "HodlStrategy")
    config = {"dry_run": True, "stake_currency": "USDT"}
    s = module.HodlStrategy(config)
    assert s.timeframe in {"1m", "5m", "15m", "1h", "4h", "1d"}


def test_template_loads():
    module = _load_module("user_data/strategies/_template_strategy.py", "_template_strategy")
    assert hasattr(module, "TemplateStrategy")
    config = {"dry_run": True, "stake_currency": "USDT"}
    s = module.TemplateStrategy(config)
    assert s.timeframe in {"1m", "5m", "15m", "1h", "4h", "1d"}
