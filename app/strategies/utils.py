"""Utilities for AI strategies."""

import logging
import uuid
from datetime import datetime
from typing import Any


def get_json_logger(name: str) -> logging.Logger:
    """Get a JSON-formatted logger."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


def generate_correlation_id() -> str:
    """Generate a unique correlation ID."""
    return str(uuid.uuid4())


def get_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat()


def calculate_position_size(
    account_balance: float, risk_percent: float, stop_loss_percent: float
) -> float:
    """Calculate position size based on risk management."""
    risk_amount = account_balance * (risk_percent / 100)
    position_size = risk_amount / (stop_loss_percent / 100)
    return min(position_size, account_balance * 0.95)  # Max 95% of balance


def validate_signal(signal: dict[str, Any]) -> bool:
    """Validate a trading signal."""
    required_fields = ["symbol", "action", "confidence"]

    for field in required_fields:
        if field not in signal:
            return False

    if signal["confidence"] < 0 or signal["confidence"] > 1:
        return False

    if signal["action"] not in ["buy", "sell", "hold"]:
        return False

    return True
