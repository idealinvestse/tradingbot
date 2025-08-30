from __future__ import annotations

from typing import Any

import pytest

from app.adapters.onchain.web3_adapter import OnchainClient, Web3Config


class _StubEth:
    def __init__(self, sequence: list[Any]):
        self._sequence = list(sequence)
        self.calls = 0

    def get_transaction_count(self, address: str) -> int:  # noqa: ANN001
        self.calls += 1
        if not self._sequence:
            raise RuntimeError("no more values")
        v = self._sequence.pop(0)
        if isinstance(v, Exception):
            raise v
        return int(v)


class _StubW3:
    def __init__(self, eth: _StubEth):
        self.eth = eth


def test_get_tx_count_retries_and_caches(monkeypatch):
    # Avoid sleeps during retry
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)

    eth = _StubEth([RuntimeError("timeout"), RuntimeError("ratelimit"), 7])
    w3 = _StubW3(eth)

    cfg = Web3Config()
    cfg.max_retries = 5
    cfg.retry_backoff_base_sec = 0.0
    cfg.retry_jitter_sec = 0.0

    client = OnchainClient(cfg=cfg, w3=w3)

    # First call should retry and eventually return
    count1 = client.get_tx_count("0xabc")
    assert count1 == 7
    assert eth.calls == 3

    # Second call should use cache (no extra w3 calls)
    count2 = client.get_tx_count("0xabc")
    assert count2 == 7
    assert eth.calls == 3


def test_init_without_provider_but_with_w3_ok():
    eth = _StubEth([5])
    w3 = _StubW3(eth)
    cfg = Web3Config()
    cfg.provider_url = ""  # explicit empty

    client = OnchainClient(cfg=cfg, w3=w3)
    assert client.get_tx_count("0x1") == 5


def test_init_requires_provider_if_no_w3():
    cfg = Web3Config()
    cfg.provider_url = ""
    with pytest.raises(ValueError):
        OnchainClient(cfg=cfg)
