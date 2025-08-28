"""Ensemble strategy voting system."""

from collections import Counter
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from app.strategies.utils import get_json_logger

logger = get_json_logger("ensemble")


class VotingConfig(BaseModel):
    """Ensemble voting configuration."""
    
    voting_method: str = "weighted"  # majority, weighted, confidence
    min_agreement: float = 0.5  # Minimum agreement threshold
    confidence_threshold: float = 0.6
    weights: Optional[Dict[str, float]] = None
    
    
class StrategySignal(BaseModel):
    """Individual strategy signal."""
    
    strategy_name: str
    signal: str  # buy, sell, hold
    confidence: float = Field(ge=0, le=1)
    metadata: Dict = Field(default_factory=dict)
    

class EnsembleVoter:
    """Combine multiple strategy signals through voting."""
    
    def __init__(self, config: VotingConfig = None):
        """Initialize ensemble voter."""
        self.config = config or VotingConfig()
        self.voting_history = []
        
    def vote(self, signals: List[StrategySignal]) -> Tuple[str, float]:
        """
        Combine signals through voting.
        
        Returns:
            Tuple of (final_signal, confidence)
        """
        if not signals:
            return "hold", 0.0
            
        if self.config.voting_method == "majority":
            return self._majority_vote(signals)
        elif self.config.voting_method == "weighted":
            return self._weighted_vote(signals)
        elif self.config.voting_method == "confidence":
            return self._confidence_vote(signals)
        else:
            return self._majority_vote(signals)
    
    def _majority_vote(self, signals: List[StrategySignal]) -> Tuple[str, float]:
        """Simple majority voting."""
        votes = [s.signal for s in signals]
        vote_counts = Counter(votes)
        
        total_votes = len(votes)
        most_common = vote_counts.most_common(1)[0]
        
        signal = most_common[0]
        confidence = most_common[1] / total_votes
        
        if confidence < self.config.min_agreement:
            return "hold", confidence
            
        return signal, confidence
    
    def _weighted_vote(self, signals: List[StrategySignal]) -> Tuple[str, float]:
        """Weighted voting based on strategy weights."""
        weights = self.config.weights or {}
        
        vote_weights = {"buy": 0, "sell": 0, "hold": 0}
        total_weight = 0
        
        for signal in signals:
            weight = weights.get(signal.strategy_name, 1.0)
            vote_weights[signal.signal] += weight * signal.confidence
            total_weight += weight
        
        if total_weight == 0:
            return "hold", 0.0
        
        # Normalize weights
        for key in vote_weights:
            vote_weights[key] /= total_weight
        
        # Get signal with highest weight
        final_signal = max(vote_weights, key=vote_weights.get)
        confidence = vote_weights[final_signal]
        
        if confidence < self.config.confidence_threshold:
            return "hold", confidence
            
        return final_signal, confidence
    
    def _confidence_vote(self, signals: List[StrategySignal]) -> Tuple[str, float]:
        """Vote based on confidence scores."""
        confidence_sums = {"buy": 0, "sell": 0, "hold": 0}
        confidence_counts = {"buy": 0, "sell": 0, "hold": 0}
        
        for signal in signals:
            confidence_sums[signal.signal] += signal.confidence
            confidence_counts[signal.signal] += 1
        
        # Calculate average confidence per signal
        avg_confidence = {}
        for sig in confidence_sums:
            if confidence_counts[sig] > 0:
                avg_confidence[sig] = confidence_sums[sig] / confidence_counts[sig]
            else:
                avg_confidence[sig] = 0
        
        # Get signal with highest average confidence
        final_signal = max(avg_confidence, key=avg_confidence.get)
        confidence = avg_confidence[final_signal]
        
        if confidence < self.config.confidence_threshold:
            return "hold", confidence
            
        return final_signal, confidence
    
    def record_outcome(self, signals: List[StrategySignal], actual_outcome: str, profit: float):
        """Record voting outcome for analysis."""
        self.voting_history.append({
            "signals": signals,
            "outcome": actual_outcome,
            "profit": profit,
            "timestamp": pd.Timestamp.now()
        })
    
    def analyze_performance(self) -> Dict:
        """Analyze ensemble performance."""
        if not self.voting_history:
            return {}
        
        correct_predictions = 0
        total_profit = 0
        
        for record in self.voting_history:
            voted_signal, _ = self.vote(record["signals"])
            if voted_signal == record["outcome"]:
                correct_predictions += 1
            total_profit += record["profit"]
        
        return {
            "accuracy": correct_predictions / len(self.voting_history),
            "total_profit": total_profit,
            "avg_profit": total_profit / len(self.voting_history),
            "total_votes": len(self.voting_history)
        }


class AdaptiveEnsemble:
    """Adaptive ensemble that adjusts weights based on performance."""
    
    def __init__(self, initial_weights: Optional[Dict[str, float]] = None):
        """Initialize adaptive ensemble."""
        self.weights = initial_weights or {}
        self.performance_history = {}
        self.voter = EnsembleVoter(VotingConfig(weights=self.weights))
        
    def update_weights(self, strategy_performances: Dict[str, float]):
        """Update strategy weights based on performance."""
        # Normalize performances to sum to 1
        total_perf = sum(strategy_performances.values())
        
        if total_perf > 0:
            for strategy, perf in strategy_performances.items():
                self.weights[strategy] = perf / total_perf
        
        # Update voter config
        self.voter.config.weights = self.weights
        logger.info(f"Updated ensemble weights: {self.weights}")
    
    def adaptive_vote(self, signals: List[StrategySignal]) -> Tuple[str, float]:
        """Vote with adaptive weights."""
        return self.voter.vote(signals)
    
    def track_performance(self, strategy_name: str, profit: float):
        """Track individual strategy performance."""
        if strategy_name not in self.performance_history:
            self.performance_history[strategy_name] = []
        
        self.performance_history[strategy_name].append(profit)
    
    def rebalance_weights(self, lookback: int = 100):
        """Rebalance weights based on recent performance."""
        strategy_performances = {}
        
        for strategy, profits in self.performance_history.items():
            recent_profits = profits[-lookback:] if len(profits) > lookback else profits
            
            if recent_profits:
                # Calculate Sharpe-like metric
                avg_profit = np.mean(recent_profits)
                std_profit = np.std(recent_profits)
                
                if std_profit > 0:
                    performance = avg_profit / std_profit
                else:
                    performance = avg_profit
                
                strategy_performances[strategy] = max(0, performance)  # No negative weights
        
        self.update_weights(strategy_performances)
