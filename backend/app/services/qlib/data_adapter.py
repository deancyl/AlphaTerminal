"""
Data Adapter for Qlib Integration

Converts AlphaTerminal's DataFrame format to Qlib's Dataset format.
Handles symbol mapping, date alignment, and feature generation.
"""
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum

logger = logging.getLogger(__name__)


class SymbolFormat(Enum):
    ALPHA_TERMINAL = "alpha_terminal"
    QLIB = "qlib"


class DataAdapter:
    """
    Adapter for converting AlphaTerminal data to Qlib format.
    
    AlphaTerminal format:
        - Symbols: sh600519, sz000001
        - DataFrame columns: date, open, high, low, close, volume
        
    Qlib format:
        - Symbols: SH600519, SZ000001
        - Dataset with instrument and time index
    """
    
    SYMBOL_PREFIX_MAP = {
        "sh": "SH",
        "sz": "SZ",
        "hk": "HK",
        "us": "US",
    }
    
    def __init__(self):
        self._symbol_cache: Dict[str, str] = {}
    
    def convert_symbol(self, symbol: str, to_format: SymbolFormat = SymbolFormat.QLIB) -> str:
        """Convert symbol between AlphaTerminal and Qlib formats."""
        if symbol in self._symbol_cache:
            return self._symbol_cache[symbol]
        
        symbol_lower = symbol.lower()
        
        if to_format == SymbolFormat.QLIB:
            for prefix, qlib_prefix in self.SYMBOL_PREFIX_MAP.items():
                if symbol_lower.startswith(prefix):
                    converted = qlib_prefix + symbol_lower[len(prefix):]
                    self._symbol_cache[symbol] = converted
                    return converted
            return symbol.upper()
        else:
            for qlib_prefix, prefix in self.SYMBOL_PREFIX_MAP.items():
                if symbol.upper().startswith(qlib_prefix):
                    converted = prefix + symbol[len(qlib_prefix):].lower()
                    self._symbol_cache[symbol] = converted
                    return converted
            return symbol.lower()
    
    def convert_dataframe(
        self,
        df: pd.DataFrame,
        symbol: str,
        date_column: str = "date",
    ) -> pd.DataFrame:
        """
        Convert AlphaTerminal DataFrame to Qlib format.
        
        Args:
            df: DataFrame with columns [date, open, high, low, close, volume]
            symbol: Stock symbol in AlphaTerminal format
            date_column: Name of date column
            
        Returns:
            DataFrame in Qlib format with MultiIndex (instrument, datetime)
        """
        if df is None or len(df) == 0:
            return pd.DataFrame()
        
        df = df.copy()
        
        qlib_symbol = self.convert_symbol(symbol, SymbolFormat.QLIB)
        
        if date_column in df.columns:
            df["datetime"] = pd.to_datetime(df[date_column])
        elif isinstance(df.index, pd.DatetimeIndex):
            df["datetime"] = df.index
        else:
            df["datetime"] = pd.to_datetime(df.index)
        
        df["instrument"] = qlib_symbol
        
        column_map = {
            "open": "$open",
            "high": "$high",
            "low": "$low",
            "close": "$close",
            "volume": "$volume",
        }
        
        for old_col, new_col in column_map.items():
            if old_col in df.columns:
                df[new_col] = df[old_col]
        
        qlib_columns = ["$open", "$high", "$low", "$close", "$volume"]
        available_columns = [c for c in qlib_columns if c in df.columns]
        
        result = df[["instrument", "datetime"] + available_columns].copy()
        result = result.set_index(["instrument", "datetime"])
        
        return result
    
    def convert_batch(
        self,
        data_dict: Dict[str, pd.DataFrame],
        date_column: str = "date",
    ) -> pd.DataFrame:
        """
        Convert multiple DataFrames to Qlib format.
        
        Args:
            data_dict: Dict mapping symbols to DataFrames
            date_column: Name of date column
            
        Returns:
            Combined DataFrame in Qlib format
        """
        converted_dfs = []
        
        for symbol, df in data_dict.items():
            converted = self.convert_dataframe(df, symbol, date_column)
            if len(converted) > 0:
                converted_dfs.append(converted)
        
        if not converted_dfs:
            return pd.DataFrame()
        
        return pd.concat(converted_dfs)
    
    def create_qlib_dataset(
        self,
        df: pd.DataFrame,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Any:
        """
        Create Qlib Dataset from DataFrame.
        
        Args:
            df: DataFrame in Qlib format
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Qlib Dataset object or None if Qlib not available
        """
        try:
            from qlib.data.dataset import DatasetH
            from qlib.data.dataset.handler import DataHandlerLP
            
            if len(df) == 0:
                return None
            
            handler = DataHandlerLP(
                data=df,
                start_time=start_date or df.index.get_level_values(1).min(),
                end_time=end_date or df.index.get_level_values(1).max(),
            )
            
            return DatasetH(handler=handler)
            
        except ImportError:
            logger.warning("[DataAdapter] Qlib not available, returning None")
            return None
    
    def extract_features(
        self,
        df: pd.DataFrame,
        feature_columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Extract features from DataFrame for ML model input.
        
        Args:
            df: DataFrame with OHLCV data
            feature_columns: Columns to use as features
            
        Returns:
            DataFrame with features
        """
        if df is None or len(df) == 0:
            return pd.DataFrame()
        
        features = df.copy()
        
        if feature_columns is None:
            feature_columns = ["$open", "$high", "$low", "$close", "$volume"]
        
        available = [c for c in feature_columns if c in features.columns]
        
        return features[available]
