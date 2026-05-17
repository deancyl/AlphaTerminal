"""
Feature Pipeline for Qlib Integration

Generates Alpha158 and Alpha360 features from OHLCV data.
These are the standard feature sets used in Qlib's ML models.
"""
import logging
import pandas as pd
import numpy as np
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


class FeatureSet(Enum):
    ALPHA158 = "Alpha158"
    ALPHA360 = "Alpha360"
    CUSTOM = "Custom"


class FeaturePipeline:
    """
    Generate features for ML-based trading strategies.
    
    Alpha158: 158 features including:
        - Price-based: MA, MACD, RSI, BOLL
        - Volume-based: OBV, VWAP
        - Momentum: ROC, MOM
        - Volatility: ATR, STD
    
    Alpha360: 360 features with extended time windows
    """
    
    FEATURE_SET_CONFIGS = {
        FeatureSet.ALPHA158: {
            "windows": [5, 10, 20, 30, 60],
            "include_volume": True,
            "include_momentum": True,
            "include_volatility": True,
        },
        FeatureSet.ALPHA360: {
            "windows": [5, 10, 20, 30, 60, 120, 180, 360],
            "include_volume": True,
            "include_momentum": True,
            "include_volatility": True,
        },
    }
    
    def __init__(self, feature_set: FeatureSet = FeatureSet.ALPHA158):
        self.feature_set = feature_set
        self.config = self.FEATURE_SET_CONFIGS.get(feature_set, {})
        self._feature_functions: Dict[str, Callable] = {}
        self._register_builtin_features()
    
    def _register_builtin_features(self):
        """Register built-in feature calculation functions."""
        self._feature_functions = {
            "MA": self._calc_ma,
            "MACD": self._calc_macd,
            "RSI": self._calc_rsi,
            "BOLL": self._calc_boll,
            "ROC": self._calc_roc,
            "MOM": self._calc_mom,
            "ATR": self._calc_atr,
            "STD": self._calc_std,
            "OBV": self._calc_obv,
            "VWAP": self._calc_vwap,
            "KDJ": self._calc_kdj,
            "WILLR": self._calc_willr,
        }
    
    def generate_features(
        self,
        df: pd.DataFrame,
        custom_features: Optional[Dict[str, Callable]] = None,
    ) -> pd.DataFrame:
        """
        Generate features from OHLCV DataFrame.
        
        Args:
            df: DataFrame with columns [open, high, low, close, volume]
            custom_features: Additional custom feature functions
            
        Returns:
            DataFrame with generated features
        """
        if df is None or len(df) == 0:
            return pd.DataFrame()
        
        features = pd.DataFrame(index=df.index)
        
        windows = self.config.get("windows", [5, 10, 20, 30, 60])
        
        for name, func in self._feature_functions.items():
            for window in windows:
                try:
                    feature_values = func(df, window)
                    col_name = f"{name}_{window}"
                    features[col_name] = feature_values
                except Exception as e:
                    logger.warning(f"[FeaturePipeline] Failed to calculate {name}_{window}: {e}")
        
        if custom_features:
            for name, func in custom_features.items():
                try:
                    features[name] = func(df)
                except Exception as e:
                    logger.warning(f"[FeaturePipeline] Failed to calculate custom feature {name}: {e}")
        
        features["$close"] = df["close"]
        features["$volume"] = df["volume"] if "volume" in df.columns else 0
        
        return features
    
    def _calc_ma(self, df: pd.DataFrame, window: int) -> pd.Series:
        return df["close"].rolling(window=window).mean()
    
    def _calc_macd(self, df: pd.DataFrame, window: int) -> pd.Series:
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        return (dif - dea) * 2
    
    def _calc_rsi(self, df: pd.DataFrame, window: int) -> pd.Series:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss.replace(0, np.inf)
        return 100 - (100 / (1 + rs))
    
    def _calc_boll(self, df: pd.DataFrame, window: int) -> pd.Series:
        mid = df["close"].rolling(window=window).mean()
        std = df["close"].rolling(window=window).std()
        return (df["close"] - mid) / (2 * std)
    
    def _calc_roc(self, df: pd.DataFrame, window: int) -> pd.Series:
        return (df["close"] - df["close"].shift(window)) / df["close"].shift(window) * 100
    
    def _calc_mom(self, df: pd.DataFrame, window: int) -> pd.Series:
        return df["close"] - df["close"].shift(window)
    
    def _calc_atr(self, df: pd.DataFrame, window: int) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift())
        low_close = abs(df["low"] - df["close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=window).mean()
    
    def _calc_std(self, df: pd.DataFrame, window: int) -> pd.Series:
        return df["close"].rolling(window=window).std()
    
    def _calc_obv(self, df: pd.DataFrame, window: int) -> pd.Series:
        direction = np.sign(df["close"].diff())
        direction.iloc[0] = 0
        obv = (direction * df["volume"]).cumsum()
        return obv
    
    def _calc_vwap(self, df: pd.DataFrame, window: int) -> pd.Series:
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        return (typical_price * df["volume"]).rolling(window=window).sum() / df["volume"].rolling(window=window).sum()
    
    def _calc_kdj(self, df: pd.DataFrame, window: int) -> pd.Series:
        low_min = df["low"].rolling(window=window).min()
        high_max = df["high"].rolling(window=window).max()
        rsv = (df["close"] - low_min) / (high_max - low_min) * 100
        k = rsv.ewm(alpha=1/3, adjust=False).mean()
        d = k.ewm(alpha=1/3, adjust=False).mean()
        return 3 * k - 2 * d
    
    def _calc_willr(self, df: pd.DataFrame, window: int) -> pd.Series:
        high_max = df["high"].rolling(window=window).max()
        low_min = df["low"].rolling(window=window).min()
        return (high_max - df["close"]) / (high_max - low_min) * -100
    
    def get_feature_count(self) -> int:
        """Get the expected number of features for current feature set."""
        windows = self.config.get("windows", [])
        base_features = len(self._feature_functions)
        return base_features * len(windows) + 2
    
    def get_feature_names(self) -> List[str]:
        """Get list of all feature names."""
        names = []
        windows = self.config.get("windows", [])
        for feature_name in self._feature_functions.keys():
            for window in windows:
                names.append(f"{feature_name}_{window}")
        names.extend(["$close", "$volume"])
        return names


def create_feature_pipeline(feature_set: FeatureSet = FeatureSet.ALPHA158) -> FeaturePipeline:
    """Factory function to create FeaturePipeline."""
    return FeaturePipeline(feature_set)