"""Monte Carlo simulation for risk analysis."""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel
from scipy import stats

from app.strategies.utils import get_json_logger

logger = get_json_logger("monte_carlo")


class MonteCarloConfig(BaseModel):
    """Monte Carlo simulation configuration."""
    
    num_simulations: int = 10000
    time_horizon: int = 252  # Trading days
    confidence_levels: List[float] = [0.95, 0.99]
    random_seed: Optional[int] = 42
    bootstrap_method: str = "parametric"  # parametric, historical, block
    

class MonteCarloSimulator:
    """Monte Carlo simulation for trading strategies."""
    
    def __init__(self, config: MonteCarloConfig = None):
        """Initialize Monte Carlo simulator."""
        self.config = config or MonteCarloConfig()
        if self.config.random_seed:
            np.random.seed(self.config.random_seed)
            
    def simulate_returns(self, historical_returns: pd.Series) -> np.ndarray:
        """Simulate future returns based on historical data."""
        if self.config.bootstrap_method == "parametric":
            return self._parametric_simulation(historical_returns)
        elif self.config.bootstrap_method == "historical":
            return self._historical_bootstrap(historical_returns)
        elif self.config.bootstrap_method == "block":
            return self._block_bootstrap(historical_returns)
        else:
            return self._parametric_simulation(historical_returns)
            
    def _parametric_simulation(self, returns: pd.Series) -> np.ndarray:
        """Parametric simulation assuming normal distribution."""
        mu = returns.mean()
        sigma = returns.std()
        
        simulated = np.random.normal(
            mu, sigma, 
            size=(self.config.num_simulations, self.config.time_horizon)
        )
        
        return simulated
    
    def _historical_bootstrap(self, returns: pd.Series) -> np.ndarray:
        """Historical bootstrap simulation."""
        returns_array = returns.values
        
        simulated = np.random.choice(
            returns_array,
            size=(self.config.num_simulations, self.config.time_horizon),
            replace=True
        )
        
        return simulated
    
    def _block_bootstrap(self, returns: pd.Series, block_size: int = 20) -> np.ndarray:
        """Block bootstrap to preserve autocorrelation."""
        returns_array = returns.values
        n_returns = len(returns_array)
        
        simulated = np.zeros((self.config.num_simulations, self.config.time_horizon))
        
        for sim in range(self.config.num_simulations):
            path = []
            while len(path) < self.config.time_horizon:
                # Random block start
                start_idx = np.random.randint(0, n_returns - block_size)
                block = returns_array[start_idx:start_idx + block_size]
                path.extend(block)
                
            simulated[sim] = path[:self.config.time_horizon]
            
        return simulated
    
    def calculate_var(self, portfolio_value: float, returns: np.ndarray,
                     confidence_level: float = 0.95) -> float:
        """Calculate Value at Risk."""
        portfolio_returns = portfolio_value * (1 + returns).prod(axis=1) - portfolio_value
        var_threshold = (1 - confidence_level) * 100
        var = np.percentile(portfolio_returns, var_threshold)
        
        return var
    
    def calculate_cvar(self, portfolio_value: float, returns: np.ndarray,
                      confidence_level: float = 0.95) -> float:
        """Calculate Conditional Value at Risk."""
        portfolio_returns = portfolio_value * (1 + returns).prod(axis=1) - portfolio_value
        var = self.calculate_var(portfolio_value, returns, confidence_level)
        
        # Average of returns worse than VaR
        cvar = portfolio_returns[portfolio_returns <= var].mean()
        
        return cvar
    
    def simulate_portfolio_paths(self, initial_value: float, 
                                returns: pd.Series) -> np.ndarray:
        """Simulate portfolio value paths."""
        simulated_returns = self.simulate_returns(returns)
        
        # Calculate cumulative portfolio values
        portfolio_paths = np.zeros((self.config.num_simulations, self.config.time_horizon + 1))
        portfolio_paths[:, 0] = initial_value
        
        for t in range(1, self.config.time_horizon + 1):
            portfolio_paths[:, t] = portfolio_paths[:, t-1] * (1 + simulated_returns[:, t-1])
            
        return portfolio_paths
    
    def calculate_drawdown_distribution(self, paths: np.ndarray) -> Dict:
        """Calculate drawdown statistics from simulated paths."""
        drawdowns = []
        
        for path in paths:
            running_max = np.maximum.accumulate(path)
            drawdown = (path - running_max) / running_max
            max_drawdown = drawdown.min()
            drawdowns.append(max_drawdown)
            
        return {
            "mean_drawdown": np.mean(drawdowns),
            "median_drawdown": np.median(drawdowns),
            "worst_drawdown": np.min(drawdowns),
            "drawdown_percentiles": {
                "5%": np.percentile(drawdowns, 5),
                "10%": np.percentile(drawdowns, 10),
                "25%": np.percentile(drawdowns, 25)
            }
        }
    
    def calculate_probability_metrics(self, paths: np.ndarray,
                                     initial_value: float) -> Dict:
        """Calculate probability-based metrics."""
        final_values = paths[:, -1]
        
        return {
            "prob_profit": np.mean(final_values > initial_value),
            "prob_loss": np.mean(final_values < initial_value),
            "prob_50pct_loss": np.mean(final_values < initial_value * 0.5),
            "prob_double": np.mean(final_values > initial_value * 2),
            "expected_return": (np.mean(final_values) - initial_value) / initial_value
        }


class RiskScenarioAnalyzer:
    """Analyze specific risk scenarios."""
    
    def __init__(self):
        """Initialize scenario analyzer."""
        self.simulator = MonteCarloSimulator()
        
    def stress_test(self, portfolio_value: float, returns: pd.Series,
                   scenarios: Dict[str, float]) -> Dict:
        """Run stress test scenarios."""
        results = {}
        
        for scenario_name, shock_factor in scenarios.items():
            # Apply shock to returns
            shocked_returns = returns * (1 + shock_factor)
            
            # Simulate with shocked returns
            simulated = self.simulator.simulate_returns(shocked_returns)
            
            # Calculate metrics
            var_95 = self.simulator.calculate_var(portfolio_value, simulated, 0.95)
            cvar_95 = self.simulator.calculate_cvar(portfolio_value, simulated, 0.95)
            
            results[scenario_name] = {
                "shock_factor": shock_factor,
                "var_95": var_95,
                "cvar_95": cvar_95,
                "expected_loss": np.mean(simulated.sum(axis=1)) * portfolio_value
            }
            
        return results
    
    def tail_risk_analysis(self, returns: pd.Series) -> Dict:
        """Analyze tail risk characteristics."""
        # Fit distributions to tails
        threshold = np.percentile(returns, 5)  # 5th percentile for left tail
        tail_data = returns[returns <= threshold]
        
        # Fit Generalized Pareto Distribution to tail
        shape, loc, scale = stats.genpareto.fit(tail_data)
        
        return {
            "tail_index": shape,
            "expected_shortfall": tail_data.mean(),
            "tail_probability": len(tail_data) / len(returns),
            "extreme_value_params": {
                "shape": shape,
                "location": loc,
                "scale": scale
            }
        }


class PortfolioOptimizer:
    """Optimize portfolio using Monte Carlo."""
    
    def __init__(self, config: MonteCarloConfig = None):
        """Initialize portfolio optimizer."""
        self.config = config or MonteCarloConfig()
        self.simulator = MonteCarloSimulator(config)
        
    def optimize_allocation(self, returns_dict: Dict[str, pd.Series],
                          target_return: float = 0.1,
                          max_risk: float = 0.2) -> Dict[str, float]:
        """Find optimal allocation using Monte Carlo."""
        assets = list(returns_dict.keys())
        n_assets = len(assets)
        
        best_sharpe = -np.inf
        best_weights = None
        
        for _ in range(self.config.num_simulations):
            # Random weights
            weights = np.random.random(n_assets)
            weights /= weights.sum()
            
            # Calculate portfolio metrics
            portfolio_return = 0
            portfolio_var = 0
            
            for i, asset1 in enumerate(assets):
                portfolio_return += weights[i] * returns_dict[asset1].mean()
                
                for j, asset2 in enumerate(assets):
                    cov = returns_dict[asset1].cov(returns_dict[asset2])
                    portfolio_var += weights[i] * weights[j] * cov
                    
            portfolio_std = np.sqrt(portfolio_var)
            
            # Check constraints
            if portfolio_return < target_return or portfolio_std > max_risk:
                continue
                
            # Calculate Sharpe ratio
            sharpe = portfolio_return / portfolio_std if portfolio_std > 0 else 0
            
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_weights = weights
                
        if best_weights is not None:
            return {asset: weight for asset, weight in zip(assets, best_weights)}
        else:
            # Equal weight if no solution found
            return {asset: 1/n_assets for asset in assets}
