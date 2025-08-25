# pragma pylint: disable=missing-docstring, unused-argument

import logging
from pathlib import Path

import pandas as pd

from app.reasoning.models import BaseReasoningModel, Decision

logger = logging.getLogger(__name__)


class PlaceholderMLModel(BaseReasoningModel):
    """A placeholder for a future machine learning-based reasoning model.

    This class simulates the interface of a real ML model. It 'loads' a model
    and returns a hardcoded decision, allowing the surrounding architecture
    to be built and tested without a dependency on a trained model.
    """

    def __init__(self, model_path: str | Path | None = None):
        self.model_path = model_path
        self.model = None
        if self.model_path:
            self.load_model(self.model_path)

    def load_model(self, path: str | Path) -> None:
        """Simulates loading a model from a file."""
        logger.info(f"Simulating loading model from: {path}")
        # In a real implementation, you would load a pickled model, weights, etc.
        # e.g., with joblib, pickle, or a framework-specific loader.
        self.model = {"name": "PlaceholderPredictor", "version": "0.1.0"}
        logger.info(f"Successfully 'loaded' model: {self.model}")

    def decide(self, dataframe: pd.DataFrame, metadata: dict) -> Decision:
        """Returns a hardcoded decision for demonstration purposes."""
        if not self.model:
            return Decision(action="hold", reason="Model not loaded.")

        # In a real implementation, you would:
        # 1. Preprocess the dataframe into features the model expects.
        # 2. Call self.model.predict(features).
        # 3. Interpret the prediction into a Decision object.

        logger.debug("ML model returning hardcoded 'hold' decision.")
        return Decision(
            action="hold",
            reason="PlaceholderMLModel is not implemented to make real decisions.",
            metadata=self.model,
        )
