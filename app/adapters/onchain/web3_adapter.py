from __future__ import annotations

import os
import random
import time
from typing import Any

from pydantic import BaseModel, Field

from app.strategies.logging_utils import get_json_logger


class Web3Config(BaseModel):
    """Configuration for Onchain Web3 client.

    Values default from environment variables to avoid committing secrets.
    """

    provider_url: str = Field(default_factory=lambda: os.getenv("WEB3_PROVIDER_URL", ""))
    timeout_sec: float = Field(default_factory=lambda: float(os.getenv("WEB3_TIMEOUT_SEC", "10")))
    max_retries: int = Field(default_factory=lambda: int(os.getenv("WEB3_MAX_RETRIES", "3")))
    retry_backoff_base_sec: float = Field(
        default_factory=lambda: float(os.getenv("WEB3_BACKOFF_BASE_SEC", "0.5"))
    )
    retry_jitter_sec: float = Field(
        default_factory=lambda: float(os.getenv("WEB3_BACKOFF_JITTER_SEC", "0.2"))
    )


class OnchainClient:
    """Thin Web3 wrapper with basic retry and simple in-memory caching.

    - Reads provider URL and timeouts from Web3Config.
    - Provides get_tx_count(address) with retries and jittered backoff.
    """

    def __init__(self, cfg: Web3Config | None = None, w3: Any | None = None) -> None:
        self.cfg = cfg or Web3Config()
        self._logger = get_json_logger("onchain", static_fields={"component": "onchain"})
        self._cache: dict[str, int] = {}

        if w3 is not None:
            self.w3 = w3
            return

        if not self.cfg.provider_url:
            raise ValueError("WEB3_PROVIDER_URL is required (env)")

        try:
            from web3 import HTTPProvider, Web3  # type: ignore
        except Exception as e:  # pragma: no cover - import error path
            # Allow caller to handle missing dependency gracefully
            raise RuntimeError(f"web3 import failed: {e}")

        self.w3 = Web3(
            HTTPProvider(self.cfg.provider_url, request_kwargs={"timeout": self.cfg.timeout_sec})
        )

    def get_tx_count(self, address: str) -> int:
        """Return transaction count for an address with retry and cache.

        Caches successful lookups per address for the lifetime of this client.
        """
        if not address:
            raise ValueError("address is required")

        if address in self._cache:
            return self._cache[address]

        attempts = 0
        last_exc: Exception | None = None
        while attempts < max(1, self.cfg.max_retries):
            attempts += 1
            try:
                # Common web3 API
                count = int(self.w3.eth.get_transaction_count(address))  # type: ignore[attr-defined]
                self._cache[address] = count
                return count
            except Exception as e:  # noqa: BLE001
                last_exc = e
                # Structured log and backoff
                self._logger.warning(
                    "web3_get_tx_count_error",
                    extra={"address": address, "attempt": attempts, "error": str(e)},
                )
                # Backoff (skip sleep in tests by setting base to 0)
                base = max(0.0, self.cfg.retry_backoff_base_sec)
                jitter = max(0.0, self.cfg.retry_jitter_sec)
                if base > 0 or jitter > 0:
                    time.sleep(base * (2 ** (attempts - 1)) + random.random() * jitter)

        assert last_exc is not None
        raise last_exc
