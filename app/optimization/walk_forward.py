"""Walk-forward optimization for strategy parameters."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel

from app.strategies.utils import get_json_logger

logger = get_json_logger("walk_forward")


class WalkForwardConfig(BaseModel):
    """Walk-forward optimization configuration."""

    in_sample_periods: int = 252  # Training period (days)
    out_sample_periods: int = 63  # Testing period (days)
    step_size: int = 21  # Step forward (days)
    min_samples: int = 100  # Minimum samples for optimization
    optimization_metric: str = "sharpe_ratio"
    parameter_ranges: dict[str, tuple[float, float]] = {}


@dataclass
class WalkForwardWindow:
    """Single walk-forward window."""

    window_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    optimal_params: dict[str, Any]
    in_sample_performance: dict[str, float]
    out_sample_performance: dict[str, float]


class WalkForwardOptimizer:
    """Walk-forward optimization implementation."""

    def __init__(self, config: WalkForwardConfig = None):
        """Initialize walk-forward optimizer."""
        self.config = config or WalkForwardConfig()
        self.windows = []
        self.performance_history = []

    def create_windows(self, data: pd.DataFrame) -> list[WalkForwardWindow]:
        """Create walk-forward windows from data."""
        windows = []

        start_idx = 0
        window_id = 0

        while start_idx + self.config.in_sample_periods + self.config.out_sample_periods <= len(
            data
        ):
            train_start_idx = start_idx
            train_end_idx = start_idx + self.config.in_sample_periods
            test_start_idx = train_end_idx
            test_end_idx = test_start_idx + self.config.out_sample_periods

            window = WalkForwardWindow(
                window_id=window_id,
                train_start=data.index[train_start_idx],
                train_end=data.index[train_end_idx - 1],
                test_start=data.index[test_start_idx],
                test_end=data.index[test_end_idx - 1],
                optimal_params={},
                in_sample_performance={},
                out_sample_performance={},
            )

            windows.append(window)

            start_idx += self.config.step_size
            window_id += 1

        logger.info(f"Created {len(windows)} walk-forward windows")
        return windows

    def optimize_window(
        self, window: WalkForwardWindow, data: pd.DataFrame, strategy_class: Any
    ) -> WalkForwardWindow:
        """Optimize parameters for a single window."""
        # Get training data
        train_data = data[window.train_start : window.train_end]

        # Find optimal parameters
        optimal_params = self._grid_search(train_data, strategy_class)
        window.optimal_params = optimal_params

        # Evaluate in-sample performance
        in_sample_metrics = self._evaluate_strategy(train_data, strategy_class, optimal_params)
        window.in_sample_performance = in_sample_metrics

        # Evaluate out-of-sample performance
        test_data = data[window.test_start : window.test_end]
        out_sample_metrics = self._evaluate_strategy(test_data, strategy_class, optimal_params)
        window.out_sample_performance = out_sample_metrics

        logger.info(
            f"Window {window.window_id}: IS {self.config.optimization_metric}="
            f"{in_sample_metrics.get(self.config.optimization_metric, 0):.3f}, "
            f"OOS={out_sample_metrics.get(self.config.optimization_metric, 0):.3f}"
        )

        return window

    def _grid_search(self, data: pd.DataFrame, strategy_class: Any) -> dict[str, Any]:
        """Grid search for optimal parameters."""
        best_score = -np.inf
        best_params = {}

        # Create parameter grid
        param_grid = self._create_parameter_grid()

        for params in param_grid:
            # Evaluate strategy with these parameters
            metrics = self._evaluate_strategy(data, strategy_class, params)
            score = metrics.get(self.config.optimization_metric, 0)

            if score > best_score:
                best_score = score
                best_params = params

        return best_params

    def _create_parameter_grid(self) -> list[dict[str, Any]]:
        """Create parameter combinations for grid search."""
        if not self.config.parameter_ranges:
            return [{}]

        # Simple grid generation
        param_names = list(self.config.parameter_ranges.keys())
        param_values = []

        for param, (min_val, max_val) in self.config.parameter_ranges.items():
            # Create 5 values between min and max
            values = np.linspace(min_val, max_val, 5)
            param_values.append(values)

        # Generate all combinations
        import itertools

        combinations = itertools.product(*param_values)

        param_grid = []
        for combo in combinations:
            params = {param_names[i]: val for i, val in enumerate(combo)}
            param_grid.append(params)

        return param_grid

    def _evaluate_strategy(
        self, data: pd.DataFrame, strategy_class: Any, params: dict[str, Any]
    ) -> dict[str, float]:
        """Evaluate strategy with given parameters."""
        # Initialize strategy with parameters
        strategy = strategy_class(**params)

        # Generate signals
        signals = strategy.generate_signals(data)

        # Calculate returns
        returns = self._calculate_returns(data, signals)

        # Calculate metrics
        metrics = {
            "total_return": returns.sum(),
            "sharpe_ratio": self._calculate_sharpe(returns),
            "max_drawdown": self._calculate_max_drawdown(returns),
            "win_rate": self._calculate_win_rate(returns),
            "profit_factor": self._calculate_profit_factor(returns),
        }

        return metrics

    def _calculate_returns(self, data: pd.DataFrame, signals: pd.Series) -> pd.Series:
        """Calculate returns from signals."""
        price_returns = data["close"].pct_change()
        strategy_returns = signals.shift(1) * price_returns
        return strategy_returns

    def _calculate_sharpe(self, returns: pd.Series, risk_free: float = 0.0) -> float:
        """Calculate Sharpe ratio."""
        excess_returns = returns - risk_free / 252

        if returns.std() > 0:
            return np.sqrt(252) * excess_returns.mean() / returns.std()
        return 0.0

    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown."""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()

    def _calculate_win_rate(self, returns: pd.Series) -> float:
        """Calculate win rate."""
        winning_trades = returns > 0
        return winning_trades.mean()

    def _calculate_profit_factor(self, returns: pd.Series) -> float:
        """Calculate profit factor."""
        profits = returns[returns > 0].sum()
        losses = abs(returns[returns < 0].sum())

        if losses > 0:
            return profits / losses
        return np.inf if profits > 0 else 0

    def run_optimization(self, data: pd.DataFrame, strategy_class: Any) -> dict:
        """Run complete walk-forward optimization."""
        windows = self.create_windows(data)

        for window in windows:
            self.optimize_window(window, data, strategy_class)
            self.windows.append(window)

        # Analyze results
        results = self.analyze_results()

        return results

    def analyze_results(self) -> dict:
        """Analyze walk-forward optimization results."""
        if not self.windows:
            return {}

        # Extract performance metrics
        in_sample_scores = []
        out_sample_scores = []

        for window in self.windows:
            is_score = window.in_sample_performance.get(self.config.optimization_metric, 0)
            oos_score = window.out_sample_performance.get(self.config.optimization_metric, 0)

            in_sample_scores.append(is_score)
            out_sample_scores.append(oos_score)

        # Calculate statistics
        return {
            "num_windows": len(self.windows),
            "avg_in_sample": np.mean(in_sample_scores),
            "avg_out_sample": np.mean(out_sample_scores),
            "overfitting_degree": np.mean(in_sample_scores) - np.mean(out_sample_scores),
            "consistency": np.corrcoef(in_sample_scores, out_sample_scores)[0, 1],
            "oos_sharpe": (
                np.mean(out_sample_scores) / np.std(out_sample_scores)
                if np.std(out_sample_scores) > 0
                else 0
            ),
        }


class AdaptiveParameterManager:
    """Manage strategy parameters adaptively."""

    def __init__(self, lookback_windows: int = 3):
        """Initialize adaptive parameter manager."""
        self.lookback_windows = lookback_windows
        self.optimizer = WalkForwardOptimizer()
        self.parameter_history = []

    def get_current_parameters(self, recent_windows: list[WalkForwardWindow]) -> dict[str, Any]:
        """Get current parameters based on recent optimization."""
        if not recent_windows:
            return {}

        # Use only recent windows
        windows_to_use = recent_windows[-self.lookback_windows :]

        # Weight parameters by out-of-sample performance
        weighted_params = {}
        total_weight = 0

        for window in windows_to_use:
            weight = window.out_sample_performance.get("sharpe_ratio", 1.0)
            weight = max(0, weight)  # No negative weights

            for param, value in window.optimal_params.items():
                if param not in weighted_params:
                    weighted_params[param] = 0
                weighted_params[param] += value * weight

            total_weight += weight

        # Normalize
        if total_weight > 0:
            for param in weighted_params:
                weighted_params[param] /= total_weight

        return weighted_params

    def update_parameters(self, new_window: WalkForwardWindow):
        """Update parameters with new optimization window."""
        self.parameter_history.append(new_window.optimal_params)

        # Check for parameter stability
        if len(self.parameter_history) > 2:
            stability = self._calculate_parameter_stability()

            if stability < 0.5:  # High variation
                logger.warning(f"High parameter instability detected: {stability:.2f}")

    def _calculate_parameter_stability(self) -> float:
        """Calculate parameter stability score."""
        if len(self.parameter_history) < 2:
            return 1.0

        recent = self.parameter_history[-5:]  # Last 5 sets

        # Calculate coefficient of variation for each parameter
        stabilities = []

        for param in recent[0].keys():
            values = [p.get(param, 0) for p in recent]

            if np.mean(values) > 0:
                cv = np.std(values) / np.mean(values)
                stability = 1 / (1 + cv)  # Convert to 0-1 scale
                stabilities.append(stability)

        return np.mean(stabilities) if stabilities else 0.0
