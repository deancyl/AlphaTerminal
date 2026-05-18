"""
Qlib Integration Module for AlphaTerminal

This module provides a bridge between AlphaTerminal's data infrastructure
and Microsoft Qlib's ML-based quantitative framework.

Components:
- qlib_init: Initialize Qlib with local data
- model_loader: Load and manage Qlib models
- feature_pipeline: Generate Alpha158/Alpha360 features
- data_adapter: Convert AlphaTerminal data to Qlib format
"""

from .qlib_init import QlibInitializer, is_qlib_available
from .data_adapter import DataAdapter
from .feature_pipeline import FeaturePipeline, FeatureSet

__all__ = [
    "QlibInitializer",
    "is_qlib_available",
    "DataAdapter",
    "FeaturePipeline",
    "FeatureSet",
]
