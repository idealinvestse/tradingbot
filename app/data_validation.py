"""Data quality validation module for OHLCV data."""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator

from app.strategies.utils import get_json_logger

logger = get_json_logger("data_validation")


class DataQualityMetrics(BaseModel):
    """Metrics for data quality assessment."""
    
    total_rows: int
    missing_values: Dict[str, int]
    outliers: Dict[str, int]
    duplicates: int
    gaps_detected: int
    negative_values: Dict[str, int]
    invalid_ohlc: int  # Where open/high/low/close relationships are invalid
    quality_score: float = Field(ge=0, le=1)
    
    @validator('quality_score')
    def validate_score(cls, v):
        return round(v, 4)


class OHLCVValidator:
    """Validator for OHLCV (Open, High, Low, Close, Volume) data."""
    
    def __init__(self, outlier_threshold: float = 3.0):
        """
        Initialize validator.
        
        Args:
            outlier_threshold: Z-score threshold for outlier detection
        """
        self.outlier_threshold = outlier_threshold
        self.logger = get_json_logger("ohlcv_validator")
    
    def validate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, DataQualityMetrics]:
        """
        Validate and clean OHLCV data.
        
        Args:
            df: DataFrame with OHLCV columns
            
        Returns:
            Tuple of (cleaned_df, quality_metrics)
        """
        self.logger.info("validation_start", extra={"rows": len(df)})
        
        # Create a copy for cleaning
        clean_df = df.copy()
        
        # Initialize metrics
        metrics = {
            "total_rows": len(df),
            "missing_values": {},
            "outliers": {},
            "duplicates": 0,
            "gaps_detected": 0,
            "negative_values": {},
            "invalid_ohlc": 0,
        }
        
        # Check for missing values
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in clean_df.columns:
                missing = clean_df[col].isna().sum()
                metrics["missing_values"][col] = int(missing)
                if missing > 0:
                    # Forward fill missing values
                    clean_df[col] = clean_df[col].fillna(method='ffill')
                    # Backward fill any remaining
                    clean_df[col] = clean_df[col].fillna(method='bfill')
        
        # Check for duplicates
        if 'date' in clean_df.columns:
            duplicates = clean_df.duplicated(subset=['date']).sum()
            metrics["duplicates"] = int(duplicates)
            if duplicates > 0:
                clean_df = clean_df.drop_duplicates(subset=['date'], keep='last')
        
        # Check for time gaps
        if 'date' in clean_df.columns:
            clean_df['date'] = pd.to_datetime(clean_df['date'])
            clean_df = clean_df.sort_values('date')
            time_diff = clean_df['date'].diff()
            expected_diff = time_diff.mode()[0] if len(time_diff.mode()) > 0 else pd.Timedelta(minutes=5)
            gaps = (time_diff > expected_diff * 2).sum()
            metrics["gaps_detected"] = int(gaps)
        
        # Check for negative values
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in clean_df.columns:
                negative = (clean_df[col] < 0).sum()
                metrics["negative_values"][col] = int(negative)
                if negative > 0:
                    # Set negative values to NaN and forward fill
                    clean_df.loc[clean_df[col] < 0, col] = np.nan
                    clean_df[col] = clean_df[col].fillna(method='ffill')
        
        # Check OHLC relationships
        if all(col in clean_df.columns for col in ['open', 'high', 'low', 'close']):
            invalid_ohlc = (
                (clean_df['high'] < clean_df['low']) |
                (clean_df['high'] < clean_df['open']) |
                (clean_df['high'] < clean_df['close']) |
                (clean_df['low'] > clean_df['open']) |
                (clean_df['low'] > clean_df['close'])
            ).sum()
            metrics["invalid_ohlc"] = int(invalid_ohlc)
            
            # Fix invalid OHLC relationships
            clean_df['high'] = clean_df[['open', 'high', 'low', 'close']].max(axis=1)
            clean_df['low'] = clean_df[['open', 'high', 'low', 'close']].min(axis=1)
        
        # Detect outliers using z-score
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in clean_df.columns:
                z_scores = np.abs((clean_df[col] - clean_df[col].mean()) / clean_df[col].std())
                outliers = (z_scores > self.outlier_threshold).sum()
                metrics["outliers"][col] = int(outliers)
                
                # Cap outliers at threshold
                if outliers > 0:
                    mean = clean_df[col].mean()
                    std = clean_df[col].std()
                    clean_df[col] = clean_df[col].clip(
                        lower=mean - self.outlier_threshold * std,
                        upper=mean + self.outlier_threshold * std
                    )
        
        # Calculate quality score
        total_issues = (
            sum(metrics["missing_values"].values()) +
            sum(metrics["outliers"].values()) +
            metrics["duplicates"] +
            metrics["gaps_detected"] +
            sum(metrics["negative_values"].values()) +
            metrics["invalid_ohlc"]
        )
        max_issues = metrics["total_rows"] * 6  # 6 types of issues
        quality_score = max(0, 1 - (total_issues / max_issues)) if max_issues > 0 else 1.0
        
        metrics["quality_score"] = quality_score
        
        # Create metrics object
        quality_metrics = DataQualityMetrics(**metrics)
        
        self.logger.info(
            "validation_complete",
            extra={
                "quality_score": quality_metrics.quality_score,
                "issues_fixed": total_issues
            }
        )
        
        return clean_df, quality_metrics
    
    def validate_live_tick(self, tick: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate a single live tick.
        
        Args:
            tick: Dictionary with OHLCV data
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ['open', 'high', 'low', 'close', 'volume']
        
        # Check required fields
        for field in required_fields:
            if field not in tick:
                return False, f"Missing required field: {field}"
            if tick[field] is None:
                return False, f"Null value in field: {field}"
            if tick[field] < 0:
                return False, f"Negative value in field: {field}"
        
        # Check OHLC relationships
        if tick['high'] < tick['low']:
            return False, "High is less than Low"
        if tick['high'] < max(tick['open'], tick['close']):
            return False, "High is less than Open or Close"
        if tick['low'] > min(tick['open'], tick['close']):
            return False, "Low is greater than Open or Close"
        
        return True, None


class DataCleaner:
    """Advanced data cleaning utilities."""
    
    @staticmethod
    def remove_weekends(df: pd.DataFrame) -> pd.DataFrame:
        """Remove weekend data from DataFrame."""
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df[df['date'].dt.dayofweek < 5]  # Monday=0, Sunday=6
        return df
    
    @staticmethod
    def normalize_volume(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize volume using rolling z-score."""
        if 'volume' in df.columns:
            window = 20
            df['volume_zscore'] = (
                df['volume'] - df['volume'].rolling(window).mean()
            ) / df['volume'].rolling(window).std()
            # Flag abnormal volume
            df['volume_abnormal'] = np.abs(df['volume_zscore']) > 3
        return df
    
    @staticmethod
    def detect_price_jumps(df: pd.DataFrame, threshold: float = 0.1) -> pd.DataFrame:
        """Detect significant price jumps."""
        if 'close' in df.columns:
            df['price_change'] = df['close'].pct_change()
            df['price_jump'] = np.abs(df['price_change']) > threshold
        return df
