"""Advanced risk management features for portfolio-level control."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator

from app.strategies.utils import get_json_logger

logger = get_json_logger("advanced_risk")


class PositionSize(BaseModel):
    """Position sizing calculation result."""
    
    base_size: Decimal
    risk_adjusted_size: Decimal
    kelly_size: Optional[Decimal] = None
    max_allowed_size: Decimal
    recommended_size: Decimal
    risk_amount: Decimal
    
    @validator('*', pre=True)
    def convert_to_decimal(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v


class PortfolioRisk(BaseModel):
    """Portfolio-level risk metrics."""
    
    total_exposure: Decimal
    var_95: Decimal  # Value at Risk at 95% confidence
    cvar_95: Decimal  # Conditional VaR
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    correlation_risk: float
    concentration_risk: float
    
    @validator('total_exposure', 'var_95', 'cvar_95', pre=True)
    def convert_to_decimal(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v


class DynamicPositionSizer:
    """Dynamic position sizing based on multiple factors."""
    
    def __init__(self, 
                 base_risk_per_trade: float = 0.02,
                 max_risk_per_trade: float = 0.05,
                 use_kelly: bool = True):
        """
        Initialize position sizer.
        
        Args:
            base_risk_per_trade: Base risk per trade (2% default)
            max_risk_per_trade: Maximum risk per trade (5% default)
            use_kelly: Whether to use Kelly Criterion
        """
        self.base_risk_per_trade = Decimal(str(base_risk_per_trade))
        self.max_risk_per_trade = Decimal(str(max_risk_per_trade))
        self.use_kelly = use_kelly
        self.logger = get_json_logger("position_sizer")
    
    def calculate_position_size(self,
                                account_balance: Decimal,
                                entry_price: Decimal,
                                stop_loss_price: Decimal,
                                win_rate: float = 0.5,
                                avg_win: float = 1.5,
                                avg_loss: float = 1.0,
                                volatility: Optional[float] = None,
                                correlation_factor: float = 1.0) -> PositionSize:
        """
        Calculate optimal position size.
        
        Args:
            account_balance: Total account balance
            entry_price: Entry price for the trade
            stop_loss_price: Stop loss price
            win_rate: Historical win rate
            avg_win: Average win amount
            avg_loss: Average loss amount
            volatility: Market volatility (optional)
            correlation_factor: Correlation with existing positions
            
        Returns:
            PositionSize object with recommendations
        """
        # Calculate risk per unit
        risk_per_unit = abs(entry_price - stop_loss_price)
        
        # Base position size (fixed fractional)
        risk_amount = account_balance * self.base_risk_per_trade
        base_size = risk_amount / risk_per_unit
        
        # Risk-adjusted size based on volatility
        if volatility:
            volatility_factor = Decimal(str(1 / (1 + volatility)))
            risk_adjusted_size = base_size * volatility_factor
        else:
            risk_adjusted_size = base_size
        
        # Kelly Criterion size
        kelly_size = None
        if self.use_kelly and win_rate > 0 and avg_loss > 0:
            kelly_fraction = self._calculate_kelly_fraction(win_rate, avg_win, avg_loss)
            kelly_size = account_balance * Decimal(str(kelly_fraction)) / entry_price
        
        # Apply correlation adjustment
        risk_adjusted_size *= Decimal(str(correlation_factor))
        
        # Maximum allowed size
        max_risk_amount = account_balance * self.max_risk_per_trade
        max_allowed_size = max_risk_amount / risk_per_unit
        
        # Recommended size (minimum of all calculated sizes)
        sizes = [base_size, risk_adjusted_size, max_allowed_size]
        if kelly_size:
            sizes.append(kelly_size)
        recommended_size = min(sizes)
        
        return PositionSize(
            base_size=base_size,
            risk_adjusted_size=risk_adjusted_size,
            kelly_size=kelly_size,
            max_allowed_size=max_allowed_size,
            recommended_size=recommended_size,
            risk_amount=recommended_size * risk_per_unit
        )
    
    def _calculate_kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculate Kelly fraction for position sizing."""
        if avg_loss == 0:
            return 0.0
        
        # Kelly formula: f = (p * b - q) / b
        # where p = win_rate, q = 1 - win_rate, b = avg_win / avg_loss
        b = avg_win / avg_loss
        q = 1 - win_rate
        kelly = (win_rate * b - q) / b
        
        # Apply Kelly fraction cap (typically 25% of full Kelly)
        return max(0, min(kelly * 0.25, 0.25))


class CorrelationAnalyzer:
    """Analyze correlation between strategies and positions."""
    
    def __init__(self, lookback_days: int = 30):
        """Initialize correlation analyzer."""
        self.lookback_days = lookback_days
        self.correlation_matrix: Optional[pd.DataFrame] = None
    
    def calculate_correlation_matrix(self, returns_data: Dict[str, List[float]]) -> pd.DataFrame:
        """
        Calculate correlation matrix for strategies.
        
        Args:
            returns_data: Dictionary of strategy returns
            
        Returns:
            Correlation matrix as DataFrame
        """
        df = pd.DataFrame(returns_data)
        self.correlation_matrix = df.corr()
        return self.correlation_matrix
    
    def get_portfolio_correlation_risk(self, weights: Dict[str, float]) -> float:
        """
        Calculate portfolio correlation risk.
        
        Args:
            weights: Strategy weights in portfolio
            
        Returns:
            Correlation risk score (0-1)
        """
        if self.correlation_matrix is None:
            return 0.0
        
        # Calculate weighted average correlation
        total_correlation = 0.0
        total_weight = 0.0
        
        for strat1, weight1 in weights.items():
            for strat2, weight2 in weights.items():
                if strat1 != strat2 and strat1 in self.correlation_matrix.columns:
                    correlation = self.correlation_matrix.loc[strat1, strat2]
                    total_correlation += abs(correlation) * weight1 * weight2
                    total_weight += weight1 * weight2
        
        return total_correlation / max(total_weight, 1e-10)
    
    def recommend_diversification(self, 
                                 current_positions: Dict[str, float],
                                 available_strategies: List[str]) -> List[str]:
        """
        Recommend strategies for diversification.
        
        Args:
            current_positions: Current strategy positions
            available_strategies: Available strategies to choose from
            
        Returns:
            List of recommended strategies
        """
        if self.correlation_matrix is None:
            return available_strategies[:3]  # Return top 3 if no correlation data
        
        recommendations = []
        
        for strategy in available_strategies:
            if strategy not in current_positions and strategy in self.correlation_matrix.columns:
                # Calculate average correlation with current positions
                avg_correlation = 0.0
                for pos in current_positions:
                    if pos in self.correlation_matrix.columns:
                        avg_correlation += abs(self.correlation_matrix.loc[strategy, pos])
                
                avg_correlation /= max(len(current_positions), 1)
                
                # Recommend if correlation is low
                if avg_correlation < 0.3:
                    recommendations.append(strategy)
        
        return recommendations[:5]  # Return top 5 recommendations


class PortfolioRiskManager:
    """Manage portfolio-level risk."""
    
    def __init__(self, 
                 max_portfolio_risk: float = 0.1,
                 max_correlation: float = 0.7,
                 max_concentration: float = 0.3):
        """
        Initialize portfolio risk manager.
        
        Args:
            max_portfolio_risk: Maximum portfolio risk (10% default)
            max_correlation: Maximum correlation allowed (0.7 default)
            max_concentration: Maximum position concentration (30% default)
        """
        self.max_portfolio_risk = max_portfolio_risk
        self.max_correlation = max_correlation
        self.max_concentration = max_concentration
        self.position_sizer = DynamicPositionSizer()
        self.correlation_analyzer = CorrelationAnalyzer()
        self.logger = get_json_logger("portfolio_risk")
    
    def calculate_portfolio_risk(self,
                                positions: Dict[str, Dict],
                                returns_history: pd.DataFrame) -> PortfolioRisk:
        """
        Calculate comprehensive portfolio risk metrics.
        
        Args:
            positions: Current positions with details
            returns_history: Historical returns DataFrame
            
        Returns:
            PortfolioRisk object
        """
        # Calculate total exposure
        total_exposure = Decimal('0')
        position_values = []
        
        for pos in positions.values():
            value = Decimal(str(pos.get('value', 0)))
            total_exposure += value
            position_values.append(float(value))
        
        # Calculate VaR and CVaR
        if not returns_history.empty:
            returns = returns_history.sum(axis=1)  # Portfolio returns
            var_95 = Decimal(str(np.percentile(returns, 5)))
            cvar_95 = Decimal(str(returns[returns <= float(var_95)].mean()))
            
            # Calculate Sharpe and Sortino ratios
            sharpe_ratio = float(returns.mean() / returns.std()) if returns.std() > 0 else 0.0
            downside_returns = returns[returns < 0]
            sortino_ratio = float(returns.mean() / downside_returns.std()) if len(downside_returns) > 0 else 0.0
            
            # Calculate max drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = float(drawdown.min())
        else:
            var_95 = Decimal('0')
            cvar_95 = Decimal('0')
            sharpe_ratio = 0.0
            sortino_ratio = 0.0
            max_drawdown = 0.0
        
        # Calculate correlation risk
        if len(positions) > 1:
            weights = {k: v['value'] / float(total_exposure) for k, v in positions.items()}
            correlation_risk = self.correlation_analyzer.get_portfolio_correlation_risk(weights)
        else:
            correlation_risk = 0.0
        
        # Calculate concentration risk
        if position_values:
            concentration_risk = max(position_values) / sum(position_values)
        else:
            concentration_risk = 0.0
        
        return PortfolioRisk(
            total_exposure=total_exposure,
            var_95=var_95,
            cvar_95=cvar_95,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            correlation_risk=correlation_risk,
            concentration_risk=concentration_risk
        )
    
    def check_risk_limits(self, portfolio_risk: PortfolioRisk) -> Tuple[bool, List[str]]:
        """
        Check if portfolio risk is within limits.
        
        Args:
            portfolio_risk: Current portfolio risk metrics
            
        Returns:
            Tuple of (is_within_limits, list_of_violations)
        """
        violations = []
        
        # Check correlation risk
        if portfolio_risk.correlation_risk > self.max_correlation:
            violations.append(f"Correlation risk {portfolio_risk.correlation_risk:.2f} exceeds limit {self.max_correlation}")
        
        # Check concentration risk
        if portfolio_risk.concentration_risk > self.max_concentration:
            violations.append(f"Concentration risk {portfolio_risk.concentration_risk:.2f} exceeds limit {self.max_concentration}")
        
        # Check max drawdown
        if abs(portfolio_risk.max_drawdown) > self.max_portfolio_risk:
            violations.append(f"Max drawdown {abs(portfolio_risk.max_drawdown):.2f} exceeds limit {self.max_portfolio_risk}")
        
        return len(violations) == 0, violations
    
    def rebalance_portfolio(self,
                           current_positions: Dict[str, Dict],
                           target_weights: Dict[str, float],
                           account_balance: Decimal) -> Dict[str, Dict]:
        """
        Calculate rebalancing trades.
        
        Args:
            current_positions: Current positions
            target_weights: Target portfolio weights
            account_balance: Total account balance
            
        Returns:
            Dictionary of rebalancing trades
        """
        rebalancing_trades = {}
        
        for strategy, target_weight in target_weights.items():
            target_value = account_balance * Decimal(str(target_weight))
            current_value = Decimal(str(current_positions.get(strategy, {}).get('value', 0)))
            
            difference = target_value - current_value
            
            if abs(difference) > account_balance * Decimal('0.01'):  # Only rebalance if > 1%
                rebalancing_trades[strategy] = {
                    'action': 'buy' if difference > 0 else 'sell',
                    'amount': abs(difference),
                    'current_value': current_value,
                    'target_value': target_value
                }
        
        return rebalancing_trades
