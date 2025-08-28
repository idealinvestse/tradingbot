"""Options trading strategies support."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel
from scipy.stats import norm

from app.strategies.utils import get_json_logger

logger = get_json_logger("options_trading")


class OptionType(str, Enum):
    """Option types."""
    
    CALL = "call"
    PUT = "put"


class OptionStrategy(str, Enum):
    """Common option strategies."""
    
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    COVERED_CALL = "covered_call"
    PROTECTIVE_PUT = "protective_put"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    IRON_CONDOR = "iron_condor"
    BUTTERFLY = "butterfly"
    CALENDAR_SPREAD = "calendar_spread"
    VERTICAL_SPREAD = "vertical_spread"


@dataclass
class Option:
    """Option contract representation."""
    
    symbol: str
    option_type: OptionType
    strike: float
    expiry: pd.Timestamp
    premium: float
    implied_volatility: float
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None


class BlackScholes:
    """Black-Scholes option pricing model."""
    
    @staticmethod
    def calculate_price(spot: float, strike: float, time_to_expiry: float,
                       risk_free_rate: float, volatility: float, 
                       option_type: OptionType) -> float:
        """Calculate option price using Black-Scholes."""
        d1 = (np.log(spot / strike) + 
              (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / \
             (volatility * np.sqrt(time_to_expiry))
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        if option_type == OptionType.CALL:
            price = spot * norm.cdf(d1) - strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
        else:  # PUT
            price = strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) - spot * norm.cdf(-d1)
            
        return price
    
    @staticmethod
    def calculate_greeks(spot: float, strike: float, time_to_expiry: float,
                        risk_free_rate: float, volatility: float, 
                        option_type: OptionType) -> Dict[str, float]:
        """Calculate option Greeks."""
        d1 = (np.log(spot / strike) + 
              (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / \
             (volatility * np.sqrt(time_to_expiry))
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        # Delta
        if option_type == OptionType.CALL:
            delta = norm.cdf(d1)
        else:
            delta = -norm.cdf(-d1)
            
        # Gamma (same for calls and puts)
        gamma = norm.pdf(d1) / (spot * volatility * np.sqrt(time_to_expiry))
        
        # Theta
        term1 = -spot * norm.pdf(d1) * volatility / (2 * np.sqrt(time_to_expiry))
        if option_type == OptionType.CALL:
            term2 = risk_free_rate * strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
            theta = (term1 - term2) / 365  # Daily theta
        else:
            term2 = risk_free_rate * strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2)
            theta = (term1 + term2) / 365
            
        # Vega (same for calls and puts)
        vega = spot * norm.pdf(d1) * np.sqrt(time_to_expiry) / 100  # Per 1% change in volatility
        
        # Rho
        if option_type == OptionType.CALL:
            rho = strike * time_to_expiry * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2) / 100
        else:
            rho = -strike * time_to_expiry * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) / 100
            
        return {
            "delta": delta,
            "gamma": gamma,
            "theta": theta,
            "vega": vega,
            "rho": rho
        }


class OptionsStrategyBuilder:
    """Build and analyze options strategies."""
    
    def __init__(self):
        """Initialize strategy builder."""
        self.bs_model = BlackScholes()
        
    def create_long_call(self, spot: float, strike: float, expiry: pd.Timestamp,
                        volatility: float, risk_free_rate: float = 0.05) -> Dict:
        """Create long call strategy."""
        time_to_expiry = (expiry - pd.Timestamp.now()).days / 365
        
        premium = self.bs_model.calculate_price(
            spot, strike, time_to_expiry, risk_free_rate, volatility, OptionType.CALL
        )
        
        greeks = self.bs_model.calculate_greeks(
            spot, strike, time_to_expiry, risk_free_rate, volatility, OptionType.CALL
        )
        
        return {
            "strategy": OptionStrategy.LONG_CALL,
            "legs": [
                {
                    "type": OptionType.CALL,
                    "position": 1,  # Long
                    "strike": strike,
                    "premium": premium,
                    "greeks": greeks
                }
            ],
            "max_profit": "unlimited",
            "max_loss": premium,
            "breakeven": strike + premium
        }
    
    def create_iron_condor(self, spot: float, strikes: List[float], 
                          expiry: pd.Timestamp, volatility: float,
                          risk_free_rate: float = 0.05) -> Dict:
        """Create iron condor strategy."""
        if len(strikes) != 4:
            raise ValueError("Iron condor requires 4 strikes")
            
        strikes = sorted(strikes)
        time_to_expiry = (expiry - pd.Timestamp.now()).days / 365
        
        legs = []
        net_premium = 0
        
        # Buy OTM put
        premium = self.bs_model.calculate_price(
            spot, strikes[0], time_to_expiry, risk_free_rate, volatility, OptionType.PUT
        )
        legs.append({
            "type": OptionType.PUT,
            "position": 1,
            "strike": strikes[0],
            "premium": premium
        })
        net_premium -= premium
        
        # Sell OTM put
        premium = self.bs_model.calculate_price(
            spot, strikes[1], time_to_expiry, risk_free_rate, volatility, OptionType.PUT
        )
        legs.append({
            "type": OptionType.PUT,
            "position": -1,
            "strike": strikes[1],
            "premium": premium
        })
        net_premium += premium
        
        # Sell OTM call
        premium = self.bs_model.calculate_price(
            spot, strikes[2], time_to_expiry, risk_free_rate, volatility, OptionType.CALL
        )
        legs.append({
            "type": OptionType.CALL,
            "position": -1,
            "strike": strikes[2],
            "premium": premium
        })
        net_premium += premium
        
        # Buy OTM call
        premium = self.bs_model.calculate_price(
            spot, strikes[3], time_to_expiry, risk_free_rate, volatility, OptionType.CALL
        )
        legs.append({
            "type": OptionType.CALL,
            "position": 1,
            "strike": strikes[3],
            "premium": premium
        })
        net_premium -= premium
        
        return {
            "strategy": OptionStrategy.IRON_CONDOR,
            "legs": legs,
            "max_profit": net_premium,
            "max_loss": (strikes[1] - strikes[0]) - net_premium,
            "breakeven_low": strikes[1] - net_premium,
            "breakeven_high": strikes[2] + net_premium,
            "profit_range": (strikes[1], strikes[2])
        }
    
    def calculate_payoff(self, strategy: Dict, spot_prices: np.ndarray) -> np.ndarray:
        """Calculate strategy payoff at different spot prices."""
        payoffs = np.zeros_like(spot_prices)
        
        for leg in strategy["legs"]:
            position = leg["position"]
            strike = leg["strike"]
            premium = leg["premium"]
            option_type = leg["type"]
            
            for i, spot in enumerate(spot_prices):
                if option_type == OptionType.CALL:
                    intrinsic_value = max(0, spot - strike)
                else:  # PUT
                    intrinsic_value = max(0, strike - spot)
                    
                # Account for premium paid/received
                leg_payoff = position * (intrinsic_value - premium)
                payoffs[i] += leg_payoff
                
        return payoffs


class OptionsDeltaHedger:
    """Delta hedging for options positions."""
    
    def __init__(self, rebalance_threshold: float = 0.01):
        """Initialize delta hedger."""
        self.rebalance_threshold = rebalance_threshold
        self.bs_model = BlackScholes()
        self.hedge_history = []
        
    def calculate_portfolio_delta(self, options: List[Option], spot: float,
                                 risk_free_rate: float = 0.05) -> float:
        """Calculate total portfolio delta."""
        total_delta = 0
        
        for option in options:
            time_to_expiry = (option.expiry - pd.Timestamp.now()).days / 365
            
            greeks = self.bs_model.calculate_greeks(
                spot, option.strike, time_to_expiry, 
                risk_free_rate, option.implied_volatility, option.option_type
            )
            
            total_delta += greeks["delta"]
            
        return total_delta
    
    def calculate_hedge_quantity(self, portfolio_delta: float, 
                                contract_multiplier: int = 100) -> int:
        """Calculate quantity of underlying needed for delta neutral."""
        # Number of shares to buy/sell
        hedge_shares = -portfolio_delta * contract_multiplier
        
        return round(hedge_shares)
    
    def should_rebalance(self, current_delta: float, target_delta: float = 0) -> bool:
        """Check if rebalancing is needed."""
        delta_difference = abs(current_delta - target_delta)
        return delta_difference > self.rebalance_threshold
    
    def execute_hedge(self, options: List[Option], spot: float,
                     current_hedge_position: int = 0) -> Dict:
        """Execute delta hedge."""
        portfolio_delta = self.calculate_portfolio_delta(options, spot)
        
        target_hedge = self.calculate_hedge_quantity(portfolio_delta)
        hedge_adjustment = target_hedge - current_hedge_position
        
        result = {
            "portfolio_delta": portfolio_delta,
            "current_hedge": current_hedge_position,
            "target_hedge": target_hedge,
            "adjustment": hedge_adjustment,
            "action": "buy" if hedge_adjustment > 0 else "sell" if hedge_adjustment < 0 else "none",
            "timestamp": pd.Timestamp.now()
        }
        
        self.hedge_history.append(result)
        return result


class VolatilityTrader:
    """Trade volatility using options."""
    
    def __init__(self):
        """Initialize volatility trader."""
        self.strategy_builder = OptionsStrategyBuilder()
        
    def create_volatility_bet(self, spot: float, expected_move: float,
                             expiry: pd.Timestamp, current_iv: float,
                             target_iv: float) -> Dict:
        """Create strategy based on volatility view."""
        if target_iv > current_iv:
            # Expect volatility to increase - buy straddle
            return self._create_long_straddle(spot, expiry, current_iv)
        else:
            # Expect volatility to decrease - sell straddle
            return self._create_short_straddle(spot, expiry, current_iv)
    
    def _create_long_straddle(self, spot: float, expiry: pd.Timestamp,
                              volatility: float) -> Dict:
        """Create long straddle for volatility expansion."""
        time_to_expiry = (expiry - pd.Timestamp.now()).days / 365
        
        call_premium = BlackScholes.calculate_price(
            spot, spot, time_to_expiry, 0.05, volatility, OptionType.CALL
        )
        
        put_premium = BlackScholes.calculate_price(
            spot, spot, time_to_expiry, 0.05, volatility, OptionType.PUT
        )
        
        total_premium = call_premium + put_premium
        
        return {
            "strategy": OptionStrategy.STRADDLE,
            "type": "long",
            "strike": spot,
            "total_premium": total_premium,
            "breakeven_up": spot + total_premium,
            "breakeven_down": spot - total_premium,
            "max_loss": total_premium,
            "max_profit": "unlimited"
        }
    
    def _create_short_straddle(self, spot: float, expiry: pd.Timestamp,
                               volatility: float) -> Dict:
        """Create short straddle for volatility contraction."""
        straddle = self._create_long_straddle(spot, expiry, volatility)
        
        # Reverse for short position
        straddle["type"] = "short"
        straddle["max_profit"] = straddle["total_premium"]
        straddle["max_loss"] = "unlimited"
        
        return straddle
