"""Smart order routing for optimal execution."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel

from app.strategies.utils import get_json_logger

logger = get_json_logger("smart_order_router")


class OrderType(str, Enum):
    """Order types."""
    
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"
    

class ExecutionAlgo(str, Enum):
    """Execution algorithms."""
    
    AGGRESSIVE = "aggressive"
    PASSIVE = "passive"
    ADAPTIVE = "adaptive"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"
    POV = "pov"  # Percentage of Volume
    

@dataclass
class VenueMetrics:
    """Venue performance metrics."""
    
    exchange: str
    avg_spread: float
    avg_fill_time_ms: float
    liquidity_score: float
    fee_rate: float
    reliability_score: float
    

class RouterConfig(BaseModel):
    """Smart order router configuration."""
    
    max_venues: int = 3
    min_venue_liquidity: float = 1000
    max_slippage: float = 0.002
    urgency_threshold: float = 0.8
    split_threshold: float = 10000
    iceberg_show_ratio: float = 0.1
    

class SmartOrderRouter:
    """Route orders optimally across venues."""
    
    def __init__(self, config: RouterConfig = None):
        """Initialize smart order router."""
        self.config = config or RouterConfig()
        self.venue_metrics = {}
        self.routing_history = []
        
    def route_order(self, symbol: str, side: str, quantity: float,
                   order_type: OrderType, urgency: float = 0.5,
                   market_data: Dict = None) -> List[Dict]:
        """
        Route order across venues.
        
        Args:
            symbol: Trading symbol
            side: buy/sell
            quantity: Order quantity
            order_type: Type of order
            urgency: 0-1 scale (1 = most urgent)
            market_data: Current market data per venue
            
        Returns:
            List of child orders per venue
        """
        # Select best venues
        venues = self._select_venues(symbol, quantity, market_data)
        
        # Choose execution algorithm
        algo = self._select_algorithm(quantity, urgency, order_type)
        
        # Split order across venues
        child_orders = self._split_order(
            symbol, side, quantity, order_type, algo, venues, market_data
        )
        
        # Record routing decision
        self._record_routing(symbol, side, quantity, child_orders)
        
        return child_orders
    
    def _select_venues(self, symbol: str, quantity: float, 
                      market_data: Dict) -> List[str]:
        """Select best venues for execution."""
        venue_scores = {}
        
        for venue, data in market_data.items():
            if symbol not in data:
                continue
                
            score = self._calculate_venue_score(venue, symbol, quantity, data[symbol])
            venue_scores[venue] = score
            
        # Sort by score and select top venues
        sorted_venues = sorted(venue_scores.items(), key=lambda x: x[1], reverse=True)
        selected = [v[0] for v in sorted_venues[:self.config.max_venues]]
        
        logger.info(f"Selected venues: {selected}")
        return selected
    
    def _calculate_venue_score(self, venue: str, symbol: str, 
                              quantity: float, market_data: Dict) -> float:
        """Calculate venue score for routing."""
        score = 0.0
        
        # Liquidity score
        if "orderbook" in market_data:
            book = market_data["orderbook"]
            available_liquidity = sum([level[1] for level in book.get("bids", [])])
            liquidity_ratio = min(available_liquidity / quantity, 1.0)
            score += liquidity_ratio * 40
            
        # Spread score
        if "bid" in market_data and "ask" in market_data:
            spread = (market_data["ask"] - market_data["bid"]) / market_data["bid"]
            spread_score = max(0, 1 - spread * 100)  # Lower spread = higher score
            score += spread_score * 30
            
        # Fee score
        metrics = self.venue_metrics.get(venue)
        if metrics:
            fee_score = max(0, 1 - metrics.fee_rate * 100)
            score += fee_score * 20
            
            # Reliability score
            score += metrics.reliability_score * 10
            
        return score
    
    def _select_algorithm(self, quantity: float, urgency: float, 
                        order_type: OrderType) -> ExecutionAlgo:
        """Select execution algorithm."""
        if urgency > self.config.urgency_threshold:
            return ExecutionAlgo.AGGRESSIVE
            
        if quantity > self.config.split_threshold:
            if order_type == OrderType.LIMIT:
                return ExecutionAlgo.ICEBERG
            else:
                return ExecutionAlgo.TWAP
                
        return ExecutionAlgo.ADAPTIVE
    
    def _split_order(self, symbol: str, side: str, quantity: float,
                    order_type: OrderType, algo: ExecutionAlgo,
                    venues: List[str], market_data: Dict) -> List[Dict]:
        """Split order across venues."""
        child_orders = []
        
        if algo == ExecutionAlgo.ICEBERG:
            return self._split_iceberg(symbol, side, quantity, order_type, venues)
        elif algo == ExecutionAlgo.TWAP:
            return self._split_twap(symbol, side, quantity, order_type, venues)
        elif algo == ExecutionAlgo.VWAP:
            return self._split_vwap(symbol, side, quantity, order_type, venues, market_data)
        else:
            return self._split_proportional(symbol, side, quantity, order_type, venues, market_data)
    
    def _split_proportional(self, symbol: str, side: str, quantity: float,
                           order_type: OrderType, venues: List[str],
                           market_data: Dict) -> List[Dict]:
        """Split order proportionally based on liquidity."""
        child_orders = []
        
        # Calculate liquidity per venue
        venue_liquidity = {}
        total_liquidity = 0
        
        for venue in venues:
            if venue in market_data and symbol in market_data[venue]:
                book = market_data[venue][symbol].get("orderbook", {})
                liquidity = sum([level[1] for level in book.get("bids" if side == "sell" else "asks", [])])
                venue_liquidity[venue] = liquidity
                total_liquidity += liquidity
                
        # Split quantity proportionally
        remaining = quantity
        for venue in venues:
            if total_liquidity > 0:
                proportion = venue_liquidity.get(venue, 0) / total_liquidity
                venue_quantity = min(quantity * proportion, remaining)
            else:
                venue_quantity = quantity / len(venues)
                
            child_orders.append({
                "venue": venue,
                "symbol": symbol,
                "side": side,
                "quantity": venue_quantity,
                "order_type": order_type.value,
                "algorithm": ExecutionAlgo.ADAPTIVE.value
            })
            
            remaining -= venue_quantity
            
        return child_orders
    
    def _split_iceberg(self, symbol: str, side: str, quantity: float,
                      order_type: OrderType, venues: List[str]) -> List[Dict]:
        """Split as iceberg orders."""
        show_quantity = quantity * self.config.iceberg_show_ratio
        
        child_orders = []
        for venue in venues:
            child_orders.append({
                "venue": venue,
                "symbol": symbol,
                "side": side,
                "quantity": quantity / len(venues),
                "show_quantity": show_quantity / len(venues),
                "order_type": OrderType.ICEBERG.value,
                "algorithm": ExecutionAlgo.ICEBERG.value
            })
            
        return child_orders
    
    def _split_twap(self, symbol: str, side: str, quantity: float,
                   order_type: OrderType, venues: List[str]) -> List[Dict]:
        """Split for TWAP execution."""
        time_slices = 10  # Execute over 10 time periods
        slice_quantity = quantity / time_slices
        
        child_orders = []
        for venue in venues:
            for i in range(time_slices):
                child_orders.append({
                    "venue": venue,
                    "symbol": symbol,
                    "side": side,
                    "quantity": slice_quantity / len(venues),
                    "order_type": order_type.value,
                    "algorithm": ExecutionAlgo.TWAP.value,
                    "time_slice": i,
                    "delay_seconds": i * 60  # 1 minute between slices
                })
                
        return child_orders
    
    def _split_vwap(self, symbol: str, side: str, quantity: float,
                   order_type: OrderType, venues: List[str],
                   market_data: Dict) -> List[Dict]:
        """Split for VWAP execution."""
        # Use historical volume profile
        volume_profile = self._get_volume_profile(symbol, market_data)
        
        child_orders = []
        for venue in venues:
            for time_bucket, volume_pct in volume_profile.items():
                child_orders.append({
                    "venue": venue,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity * volume_pct / len(venues),
                    "order_type": order_type.value,
                    "algorithm": ExecutionAlgo.VWAP.value,
                    "time_bucket": time_bucket
                })
                
        return child_orders
    
    def _get_volume_profile(self, symbol: str, market_data: Dict) -> Dict[int, float]:
        """Get intraday volume profile."""
        # Simplified volume profile
        return {
            9: 0.15,   # 9am: 15% of volume
            10: 0.20,  # 10am: 20% of volume
            11: 0.15,  # 11am: 15% of volume
            12: 0.10,  # 12pm: 10% of volume
            13: 0.10,  # 1pm: 10% of volume
            14: 0.15,  # 2pm: 15% of volume
            15: 0.15   # 3pm: 15% of volume
        }
    
    def _record_routing(self, symbol: str, side: str, quantity: float,
                       child_orders: List[Dict]):
        """Record routing decision for analysis."""
        self.routing_history.append({
            "timestamp": pd.Timestamp.now(),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "child_orders": child_orders,
            "venue_count": len(set([o["venue"] for o in child_orders]))
        })


class ExecutionAnalyzer:
    """Analyze execution quality."""
    
    def __init__(self):
        """Initialize execution analyzer."""
        self.executions = []
        
    def analyze_execution(self, intended_price: float, executed_orders: List[Dict]) -> Dict:
        """Analyze execution quality."""
        total_quantity = sum([o["filled_quantity"] for o in executed_orders])
        total_value = sum([o["filled_quantity"] * o["avg_price"] for o in executed_orders])
        
        if total_quantity == 0:
            return {"error": "No execution"}
            
        avg_price = total_value / total_quantity
        slippage = (avg_price - intended_price) / intended_price
        
        # Calculate execution metrics
        metrics = {
            "avg_price": avg_price,
            "slippage": slippage,
            "slippage_bps": slippage * 10000,  # Basis points
            "total_quantity": total_quantity,
            "fill_rate": total_quantity / sum([o["quantity"] for o in executed_orders]),
            "venue_distribution": self._calculate_venue_distribution(executed_orders)
        }
        
        self.executions.append(metrics)
        return metrics
    
    def _calculate_venue_distribution(self, executed_orders: List[Dict]) -> Dict:
        """Calculate distribution across venues."""
        venue_quantities = {}
        
        for order in executed_orders:
            venue = order["venue"]
            quantity = order["filled_quantity"]
            
            if venue not in venue_quantities:
                venue_quantities[venue] = 0
            venue_quantities[venue] += quantity
            
        total = sum(venue_quantities.values())
        
        if total > 0:
            return {v: q/total for v, q in venue_quantities.items()}
        return {}
    
    def get_execution_stats(self) -> Dict:
        """Get overall execution statistics."""
        if not self.executions:
            return {}
            
        slippages = [e["slippage_bps"] for e in self.executions]
        fill_rates = [e["fill_rate"] for e in self.executions]
        
        return {
            "avg_slippage_bps": np.mean(slippages),
            "std_slippage_bps": np.std(slippages),
            "avg_fill_rate": np.mean(fill_rates),
            "total_executions": len(self.executions),
            "positive_slippage_pct": sum([1 for s in slippages if s > 0]) / len(slippages)
        }
