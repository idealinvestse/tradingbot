"""AI Strategy Registry for managing all AI-powered trading"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.strategies.utils import get_json_logger

logger = get_json_logger("ai_strategy_registry")


class AIStrategyType(str, Enum):
    """AI strategy types from GROK.md."""
    
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    PREDICTIVE_MODELING = "predictive_modeling"
    REINFORCEMENT_LEARNING = "reinforcement_learning"
    ARBITRAGE = "arbitrage"
    GRID_TRADING = "grid_trading"
    MOMENTUM_TRADING = "momentum_trading"
    PORTFOLIO_REBALANCING = "portfolio_rebalancing"
    DCA_TIMING = "dca_timing"
    HIGH_FREQUENCY_TRADING = "hft"
    NARRATIVE_DETECTION = "narrative_detection"


class AIStrategyConfig(BaseModel):
    """Configuration for an AI strategy."""
    
    name: str
    strategy_type: AIStrategyType
    description: str
    mechanics: str
    why_effective: str
    example: str
    bots: List[str] = Field(default_factory=list)
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    performance_metrics: str
    insights_2025: str = Field(alias="2025_insights")
    
    # Strategy-specific parameters
    enabled: bool = True
    min_confidence: float = 0.6
    max_risk_per_trade: float = 0.02  # 2% max risk
    lookback_period: int = 100
    rebalance_threshold: float = 0.05
    
    # ML model settings
    model_type: Optional[str] = None
    model_version: Optional[str] = None
    feature_set: Optional[List[str]] = None
    
    class Config:
        """Pydantic config."""
        populate_by_name = True


class AIStrategyRegistry:
    """Central registry for all AI strategies."""
    
    def __init__(self):
        """Initialize the registry."""
        self.strategies: Dict[str, AIStrategyConfig] = {}
        self._load_default_strategies()
        
    def _load_default_strategies(self):
        """Load default strategies from GROK.md definitions."""
        default_strategies = [
            {
                "name": "AI-Driven Sentiment Analysis",
                "strategy_type": AIStrategyType.SENTIMENT_ANALYSIS,
                "description": "Analyzes social media and news for market mood using NLP",
                "mechanics": "NLP models quantify sentiment scores (-1 to 1), trigger trades with volume confirmation",
                "why_effective": "Handles 80% emotion-driven volatility with 70-85% accuracy",
                "example": "Bot buys SOL at $150 on positive surge, sells at $180 for 35%",
                "bots": ["Token Metrics", "Quadency", "3Commas"],
                "pros": ["Early insights", "Emotion-free"],
                "cons": ["Volatile data", "Manipulation vulnerability"],
                "risks": ["Fake news", "Regulatory scrutiny"],
                "performance_metrics": "70-85% accuracy in backtests",
                "2025_insights": "Thrives with ETF booms; integrated in bots for altcoin hype",
                "model_type": "BERT",
                "min_confidence": 0.7
            },
            {
                "name": "Machine Learning Predictive Modeling",
                "strategy_type": AIStrategyType.PREDICTIVE_MODELING,
                "description": "Forecasts prices using historical patterns",
                "mechanics": "LSTM/random forests analyze price/on-chain/macro data for signals",
                "why_effective": "75% correlations uncovered, 40% false positive reduction vs TA",
                "example": "Predicts ETH 15% rise, enters $3,000/exits $3,450 for 28% monthly",
                "bots": ["Numerai", "Cryptohopper", "Intellectia.ai"],
                "pros": ["Data-driven", "Scalable"],
                "cons": ["Data dependency", "Compute intensive"],
                "risks": ["Overfitting", "Black swans"],
                "performance_metrics": "28% monthly in 2025 surges",
                "2025_insights": "Essential for quant with $150k BTC potential",
                "model_type": "LSTM",
                "lookback_period": 200
            },
            {
                "name": "Reinforcement Learning Optimization",
                "strategy_type": AIStrategyType.REINFORCEMENT_LEARNING,
                "description": "Adapts strategies in real-time based on rewards",
                "mechanics": "Deep Q-networks/A2C agents reward profitable actions",
                "why_effective": "50% improvement over static bots in volatility",
                "example": "ADA bot hedges bear dip, turns 10% loss to 15% gain",
                "bots": ["3Commas", "Intellectia.ai", "HaasOnline"],
                "pros": ["Real-time learning", "Evolution-like"],
                "cons": ["High resources", "Initial poor performance"],
                "risks": ["Convergence failure", "Ethical issues"],
                "performance_metrics": "50% performance boost",
                "2025_insights": "For unpredictable assets amid market shifts",
                "model_type": "DQN"
            },
            {
                "name": "AI-Enhanced Arbitrage",
                "strategy_type": AIStrategyType.ARBITRAGE,
                "description": "Spots price discrepancies across exchanges",
                "mechanics": "ML anomaly detection scans pairs, executes via APIs",
                "why_effective": "20-30% annual with minimal drawdown",
                "example": "BTC diff nets 0.33%/trade, 45% yearly",
                "bots": ["Pionex", "Bitsgap", "Cryptohopper"],
                "pros": ["Near risk-free", "Automated"],
                "cons": ["Thin margins", "Latency needs"],
                "risks": ["Fees/delays", "Outages"],
                "performance_metrics": "20-30% annual",
                "2025_insights": "Cross-chain growth in DeFi",
                "min_confidence": 0.9,
                "max_risk_per_trade": 0.005
            },
            {
                "name": "Grid Trading with AI",
                "strategy_type": AIStrategyType.GRID_TRADING,
                "description": "Places buy/sell orders in grids, optimized by AI",
                "mechanics": "ML adjusts intervals on volatility, automates in ranges",
                "why_effective": "35% efficiency boost in passives",
                "example": "USDT/BTC grid yields 25% in consolidation",
                "bots": ["Pionex", "Bitsgap", "3Commas"],
                "pros": ["Low maintenance", "Volatility profits"],
                "cons": ["Trend failures", "Range setup"],
                "risks": ["Breaches", "Loss accumulation"],
                "performance_metrics": "35% boost",
                "2025_insights": "Adaptive for range-bound phases",
                "rebalance_threshold": 0.02
            },
            {
                "name": "Momentum Trading via AI",
                "strategy_type": AIStrategyType.MOMENTUM_TRADING,
                "description": "Rides upward trends detected by algorithms",
                "mechanics": "ML filters RSI/MACD for acceleration signals",
                "why_effective": "40% accuracy, 50-100% captures",
                "example": "LINK hype: buy $20/sell $30 for 50%",
                "bots": ["TradeSanta", "Cryptohopper", "Coinrule"],
                "pros": ["Quick gains", "Trend exploitation"],
                "cons": ["Reversal prone", "Choppy fails"],
                "risks": ["Whipsaws", "Overconfidence"],
                "performance_metrics": "40% accuracy",
                "2025_insights": "Amplified in bull cycles",
                "min_confidence": 0.65
            },
            {
                "name": "Portfolio Rebalancing with AI",
                "strategy_type": AIStrategyType.PORTFOLIO_REBALANCING,
                "description": "Automatically adjusts holdings",
                "mechanics": "Optimization algos reallocate on risk/performance",
                "why_effective": "25% drawdown cut",
                "example": "Sells BTC/buys ETH for 18% stability",
                "bots": ["Shrimpy", "Quadency", "Bitsgap"],
                "pros": ["Risk reduction", "Diversification"],
                "cons": ["Fees", "Over-rebalancing"],
                "risks": ["Volatile periods", "Tax implications"],
                "performance_metrics": "25% reduction",
                "2025_insights": "For multi-alt amid diversification",
                "rebalance_threshold": 0.1
            },
            {
                "name": "DCA with AI Timing",
                "strategy_type": AIStrategyType.DCA_TIMING,
                "description": "Invests fixed amounts at AI-predicted optimal points",
                "mechanics": "Predicts dips via sentiment/volatility for entries",
                "why_effective": "30% better averages",
                "example": "BTC weekly: 40% extra in cycles",
                "bots": ["Pionex", "CryptoHero", "3Commas"],
                "pros": ["Volatility hedge", "Accumulation"],
                "cons": ["Bull underperformance", "Timing errors"],
                "risks": ["Prolonged bears", "Opportunity cost"],
                "performance_metrics": "30% improvement",
                "2025_insights": "Long-haul with ETF booms",
                "min_confidence": 0.6
            },
            {
                "name": "High-Frequency Trading (HFT) with AI",
                "strategy_type": AIStrategyType.HIGH_FREQUENCY_TRADING,
                "description": "Executes thousands of micro-trades",
                "mechanics": "Predictive algos exploit order books at sub-second",
                "why_effective": "1-2% daily",
                "example": "Scalps 0.01% edges 100x/hour for 25% monthly",
                "bots": ["HaasOnline", "Cryptohopper"],
                "pros": ["Consistent wins", "Efficiency"],
                "cons": ["Infrastructure needs", "High costs"],
                "risks": ["Latency", "Flash crashes"],
                "performance_metrics": "1000+ trades/day",
                "2025_insights": "Expanded liquid markets",
                "max_risk_per_trade": 0.001
            },
            {
                "name": "Narrative and Trend Detection with AI",
                "strategy_type": AIStrategyType.NARRATIVE_DETECTION,
                "description": "Identifies emerging stories like AI coins",
                "mechanics": "Clustering algos scan streams for forecasts",
                "why_effective": "40% early advantage",
                "example": "Buys FET $1/sells $5 in hype",
                "bots": ["Token Metrics", "Quadency"],
                "pros": ["Foresight", "Sector booms"],
                "cons": ["False positives", "Hype dependency"],
                "risks": ["Bubbles", "Narrative shifts"],
                "performance_metrics": "40% advantage",
                "2025_insights": "AI coins, DeFi 2.0 trends",
                "min_confidence": 0.55
            }
        ]
        
        for strategy_data in default_strategies:
            try:
                strategy = AIStrategyConfig(**strategy_data)
                self.register_strategy(strategy)
            except Exception as e:
                logger.error(f"Failed to load strategy {strategy_data.get('name')}: {e}")
    
    def register_strategy(self, strategy: AIStrategyConfig) -> None:
        """Register a new AI strategy."""
        key = f"{strategy.strategy_type.value}_{strategy.name.replace(' ', '_').lower()}"
        self.strategies[key] = strategy
        logger.info(f"Registered AI strategy: {key}")
    
    def get_strategy(self, key: str) -> Optional[AIStrategyConfig]:
        """Get a strategy by key."""
        return self.strategies.get(key)
    
    def get_enabled_strategies(self) -> List[AIStrategyConfig]:
        """Get all enabled strategies."""
        return [s for s in self.strategies.values() if s.enabled]
    
    def get_strategies_by_type(self, strategy_type: AIStrategyType) -> List[AIStrategyConfig]:
        """Get strategies by type."""
        return [s for s in self.strategies.values() if s.strategy_type == strategy_type]
    
    def update_strategy_config(self, key: str, updates: Dict[str, Any]) -> bool:
        """Update strategy configuration."""
        if key in self.strategies:
            strategy = self.strategies[key]
            for field, value in updates.items():
                if hasattr(strategy, field):
                    setattr(strategy, field, value)
            logger.info(f"Updated strategy config for {key}")
            return True
        return False
    
    def get_by_type(self, strategy_type: str) -> List[AIStrategyConfig]:
        """Get all strategies of a specific type."""
        matching_strategies = []
        for strategy in self.strategies.values():
            # Check if strategy_type matches the enum value or name
            if (strategy.strategy_type.value == strategy_type or 
                strategy.strategy_type.name.lower() == strategy_type.lower()):
                matching_strategies.append(strategy)
        return matching_strategies
    
    def export_strategies_json(self) -> str:
        """Export all strategies as JSON."""
        strategies_list = [
            strategy.dict(by_alias=True) for strategy in self.strategies.values()
        ]
        return json.dumps({"strategies": strategies_list}, indent=2)
    
    def import_strategies_json(self, json_data: str) -> int:
        """Import strategies from JSON."""
        data = json.loads(json_data)
        imported_count = 0
        
        for strategy_data in data.get("strategies", []):
            try:
                strategy = AIStrategyConfig(**strategy_data)
                self.register_strategy(strategy)
                imported_count += 1
            except Exception as e:
                logger.error(f"Failed to import strategy: {e}")
        
        return imported_count
