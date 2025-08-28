"""Multi-exchange arbitrage detection and execution."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel

from app.strategies.utils import get_json_logger

logger = get_json_logger("multi_exchange_arbitrage")


class ArbitrageConfig(BaseModel):
    """Arbitrage configuration."""
    
    min_profit_threshold: float = 0.002  # 0.2% minimum profit
    max_position_size: float = 10000  # Max USD per trade
    fee_structure: Dict[str, float] = {"binance": 0.001, "kraken": 0.002, "coinbase": 0.005}
    slippage_factor: float = 0.001
    execution_delay_ms: int = 100
    

@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity."""
    
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    potential_profit: float
    profit_percentage: float
    recommended_size: float
    timestamp: pd.Timestamp
    

class ArbitrageDetector:
    """Detect arbitrage opportunities across exchanges."""
    
    def __init__(self, config: ArbitrageConfig = None):
        """Initialize arbitrage detector."""
        self.config = config or ArbitrageConfig()
        self.opportunities = []
        
    def find_opportunities(self, orderbooks: Dict[str, Dict]) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities from orderbooks.
        
        Args:
            orderbooks: {exchange: {symbol: orderbook_data}}
        """
        opportunities = []
        
        # Get all unique symbols
        all_symbols = set()
        for exchange_data in orderbooks.values():
            all_symbols.update(exchange_data.keys())
            
        for symbol in all_symbols:
            # Find exchanges trading this symbol
            exchanges_with_symbol = [
                exchange for exchange in orderbooks
                if symbol in orderbooks[exchange]
            ]
            
            if len(exchanges_with_symbol) < 2:
                continue
                
            # Check all exchange pairs
            for i, buy_exchange in enumerate(exchanges_with_symbol):
                for sell_exchange in exchanges_with_symbol[i+1:]:
                    opp = self._check_pair(
                        symbol, buy_exchange, sell_exchange, orderbooks
                    )
                    if opp:
                        opportunities.append(opp)
                        
                    # Check reverse
                    opp_reverse = self._check_pair(
                        symbol, sell_exchange, buy_exchange, orderbooks
                    )
                    if opp_reverse:
                        opportunities.append(opp_reverse)
                        
        # Sort by profit percentage
        opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        self.opportunities = opportunities
        return opportunities
    
    def _check_pair(self, symbol: str, buy_exchange: str, sell_exchange: str,
                    orderbooks: Dict) -> Optional[ArbitrageOpportunity]:
        """Check if arbitrage exists between two exchanges."""
        try:
            buy_book = orderbooks[buy_exchange][symbol]
            sell_book = orderbooks[sell_exchange][symbol]
            
            # Get best prices
            buy_price = buy_book['asks'][0][0] if buy_book['asks'] else None
            sell_price = sell_book['bids'][0][0] if sell_book['bids'] else None
            
            if not buy_price or not sell_price:
                return None
                
            # Calculate fees
            buy_fee = self.config.fee_structure.get(buy_exchange, 0.002)
            sell_fee = self.config.fee_structure.get(sell_exchange, 0.002)
            
            # Account for slippage
            buy_price_adjusted = buy_price * (1 + self.config.slippage_factor)
            sell_price_adjusted = sell_price * (1 - self.config.slippage_factor)
            
            # Calculate profit
            cost = buy_price_adjusted * (1 + buy_fee)
            revenue = sell_price_adjusted * (1 - sell_fee)
            profit_per_unit = revenue - cost
            profit_percentage = (profit_per_unit / cost) * 100
            
            if profit_percentage > self.config.min_profit_threshold * 100:
                # Calculate recommended size
                buy_liquidity = buy_book['asks'][0][1] * buy_price if buy_book['asks'] else 0
                sell_liquidity = sell_book['bids'][0][1] * sell_price if sell_book['bids'] else 0
                
                max_size = min(
                    self.config.max_position_size,
                    buy_liquidity * 0.1,  # Take max 10% of liquidity
                    sell_liquidity * 0.1
                )
                
                return ArbitrageOpportunity(
                    symbol=symbol,
                    buy_exchange=buy_exchange,
                    sell_exchange=sell_exchange,
                    buy_price=buy_price,
                    sell_price=sell_price,
                    potential_profit=profit_per_unit * (max_size / buy_price),
                    profit_percentage=profit_percentage,
                    recommended_size=max_size,
                    timestamp=pd.Timestamp.now()
                )
                
        except Exception as e:
            logger.error(f"Error checking arbitrage: {e}")
            
        return None
    
    def calculate_execution_risk(self, opportunity: ArbitrageOpportunity) -> float:
        """Calculate risk score for execution."""
        risk_score = 0.0
        
        # Execution delay risk
        delay_risk = self.config.execution_delay_ms / 1000 * 0.1  # 0.1 per second
        risk_score += delay_risk
        
        # Profit margin risk
        margin_risk = max(0, 1 - (opportunity.profit_percentage / 1.0))  # Risk increases as profit decreases
        risk_score += margin_risk * 0.5
        
        # Fee uncertainty risk
        fee_variance = 0.1  # Assume 10% variance in fees
        risk_score += fee_variance
        
        return min(risk_score, 1.0)


class ArbitrageExecutor:
    """Execute arbitrage trades."""
    
    def __init__(self, config: ArbitrageConfig = None):
        """Initialize arbitrage executor."""
        self.config = config or ArbitrageConfig()
        self.execution_history = []
        
    def execute_opportunity(self, opportunity: ArbitrageOpportunity) -> Dict:
        """
        Execute an arbitrage opportunity.
        
        Returns:
            Execution result dictionary
        """
        result = {
            "opportunity": opportunity,
            "status": "pending",
            "buy_order_id": None,
            "sell_order_id": None,
            "actual_profit": 0,
            "error": None
        }
        
        try:
            # Validate opportunity is still valid
            if not self._validate_opportunity(opportunity):
                result["status"] = "expired"
                result["error"] = "Opportunity no longer valid"
                return result
                
            # Place buy order
            buy_order = self._place_order(
                opportunity.buy_exchange,
                opportunity.symbol,
                "buy",
                opportunity.recommended_size / opportunity.buy_price,
                opportunity.buy_price
            )
            result["buy_order_id"] = buy_order.get("order_id")
            
            # Place sell order
            sell_order = self._place_order(
                opportunity.sell_exchange,
                opportunity.symbol,
                "sell",
                opportunity.recommended_size / opportunity.sell_price,
                opportunity.sell_price
            )
            result["sell_order_id"] = sell_order.get("order_id")
            
            # Calculate actual profit
            buy_cost = buy_order.get("filled_amount", 0) * buy_order.get("avg_price", opportunity.buy_price)
            sell_revenue = sell_order.get("filled_amount", 0) * sell_order.get("avg_price", opportunity.sell_price)
            
            buy_fee = buy_cost * self.config.fee_structure.get(opportunity.buy_exchange, 0.002)
            sell_fee = sell_revenue * self.config.fee_structure.get(opportunity.sell_exchange, 0.002)
            
            result["actual_profit"] = sell_revenue - sell_fee - buy_cost - buy_fee
            result["status"] = "completed"
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            logger.error(f"Arbitrage execution failed: {e}")
            
        self.execution_history.append(result)
        return result
    
    def _validate_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """Validate opportunity is still valid."""
        # Check if opportunity is not too old
        age = (pd.Timestamp.now() - opportunity.timestamp).total_seconds()
        return age < 5  # 5 seconds max age
    
    def _place_order(self, exchange: str, symbol: str, side: str, 
                     amount: float, price: float) -> Dict:
        """Place order on exchange (mock implementation)."""
        # This would interface with actual exchange APIs
        return {
            "order_id": f"{exchange}_{symbol}_{pd.Timestamp.now().timestamp()}",
            "filled_amount": amount,
            "avg_price": price,
            "status": "filled"
        }


class TriangularArbitrage:
    """Triangular arbitrage within single exchange."""
    
    def __init__(self, base_currency: str = "USDT"):
        """Initialize triangular arbitrage."""
        self.base_currency = base_currency
        
    def find_triangular_opportunities(self, exchange_data: Dict[str, Dict]) -> List[Dict]:
        """Find triangular arbitrage opportunities."""
        opportunities = []
        
        # Find all currency triangles
        triangles = self._find_triangles(list(exchange_data.keys()))
        
        for triangle in triangles:
            profit = self._calculate_triangle_profit(triangle, exchange_data)
            
            if profit > 0:
                opportunities.append({
                    "triangle": triangle,
                    "profit_percentage": profit,
                    "timestamp": pd.Timestamp.now()
                })
                
        return opportunities
    
    def _find_triangles(self, symbols: List[str]) -> List[Tuple[str, str, str]]:
        """Find possible triangular paths."""
        triangles = []
        
        # Parse symbols to find currencies
        currencies = set()
        pairs_map = {}
        
        for symbol in symbols:
            # Assume format like "BTC/USDT"
            if "/" in symbol:
                base, quote = symbol.split("/")
                currencies.add(base)
                currencies.add(quote)
                
                if base not in pairs_map:
                    pairs_map[base] = []
                pairs_map[base].append(quote)
                
        # Find triangles starting with base currency
        if self.base_currency in currencies:
            for curr1 in currencies:
                if curr1 == self.base_currency:
                    continue
                    
                for curr2 in currencies:
                    if curr2 in [self.base_currency, curr1]:
                        continue
                        
                    # Check if triangle exists
                    if (f"{curr1}/{self.base_currency}" in symbols and
                        f"{curr2}/{curr1}" in symbols and
                        f"{self.base_currency}/{curr2}" in symbols):
                        triangles.append((self.base_currency, curr1, curr2))
                        
        return triangles
    
    def _calculate_triangle_profit(self, triangle: Tuple[str, str, str], 
                                  exchange_data: Dict) -> float:
        """Calculate profit from triangular arbitrage."""
        base, curr1, curr2 = triangle
        
        try:
            # Get prices
            price1 = exchange_data[f"{curr1}/{base}"]["bid"]  # Buy curr1 with base
            price2 = exchange_data[f"{curr2}/{curr1}"]["bid"]  # Buy curr2 with curr1
            price3 = exchange_data[f"{base}/{curr2}"]["bid"]  # Buy base with curr2
            
            # Calculate profit
            final_amount = 1.0 * price1 * price2 * price3
            profit = (final_amount - 1.0) * 100
            
            return profit if profit > 0 else 0
            
        except Exception:
            return 0
