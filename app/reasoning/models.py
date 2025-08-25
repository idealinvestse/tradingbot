# pragma pylint: disable=missing-docstring

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Literal

import pandas as pd


@dataclass
class Decision:
    """Represents a decision made by a reasoning model."""

    action: Literal["buy", "sell", "hold"]
    confidence: float = 1.0
    reason: str = "No reason provided."
    metadata: dict | None = None


class BaseReasoningModel(abc.ABC):
    """Abstract base class for all reasoning models."""

    @abc.abstractmethod
    def decide(self, dataframe: pd.DataFrame, metadata: dict) -> Decision:
        """
        Analyzes the given data and makes a trading decision.

        :param dataframe: The processed OHLCV data for the asset.
        :param metadata: Dictionary containing pair, timeframe, etc.
        :return: A Decision object.
        """
        raise NotImplementedError

    def load_model(self, path: str) -> None:
        """
        Optional method to load a model from a file, e.g., for ML models.
        Default implementation does nothing.
        """
        pass
