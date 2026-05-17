"""
ML Strategy Module

Provides base classes for ML-based trading strategies that integrate
with AlphaTerminal's backtest engine and Qlib's ML framework.
"""
import logging
import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


class SignalType(Enum):
    BUY = 1
    SELL = -1
    HOLD = 0


@dataclass
class PredictionResult:
    predictions: np.ndarray
    signals: List[int]
    confidence: float = 0.0
    model_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MLStrategyConfig:
    model_id: str
    feature_set: str = "Alpha158"
    prediction_threshold: float = 0.5
    position_size_pct: float = 0.95
    max_positions: int = 1
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    retrain_interval_days: int = 30
    min_confidence: float = 0.3


class BaseMLStrategy(ABC):
    """
    Abstract base class for ML-based trading strategies.
    
    Subclasses must implement:
        - predict(): Generate predictions from features
        - generate_signals(): Convert predictions to trading signals
    """
    
    def __init__(self, config: MLStrategyConfig):
        self.config = config
        self._model: Optional[Any] = None
        self._feature_pipeline: Optional[Any] = None
        self._last_prediction: Optional[PredictionResult] = None
        self._prediction_history: List[PredictionResult] = []
    
    @abstractmethod
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Generate predictions from features."""
        pass
    
    @abstractmethod
    def generate_signals(self, predictions: np.ndarray) -> List[int]:
        """Convert predictions to trading signals."""
        pass
    
    def load_model(self) -> bool:
        from app.services.qlib.model_loader import get_model_loader
        
        loader = get_model_loader()
        model = loader.load_model(self.config.model_id)
        
        if model is not None:
            self._model = model
            logger.info(f"[MLStrategy] Loaded model: {self.config.model_id}")
            return True
        
        logger.warning(f"[MLStrategy] Failed to load model: {self.config.model_id}")
        return False
    
    def save_model(self, metrics: Optional[Dict[str, float]] = None) -> bool:
        if self._model is None:
            return False
        
        from app.services.qlib.model_loader import get_model_loader, ModelType, ModelProvider
        
        loader = get_model_loader()
        return loader.save_model(
            model=self._model,
            model_id=self.config.model_id,
            model_type=ModelType.LIGHTGBM,
            provider=ModelProvider.CUSTOM,
            feature_set=self.config.feature_set,
            metrics=metrics,
        )
    
    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        from app.services.qlib.feature_pipeline import FeaturePipeline, FeatureSet
        
        if self._feature_pipeline is None:
            feature_set = FeatureSet.ALPHA158 if self.config.feature_set == "Alpha158" else FeatureSet.ALPHA360
            self._feature_pipeline = FeaturePipeline(feature_set)
        
        return self._feature_pipeline.generate_features(df)
    
    def run_prediction(self, df: pd.DataFrame) -> PredictionResult:
        """
        Run the full prediction pipeline.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            PredictionResult with predictions and signals
        """
        features = self.generate_features(df)
        
        predictions = self.predict(features)
        
        signals = self.generate_signals(predictions)
        
        confidence = self._calculate_confidence(predictions)
        
        result = PredictionResult(
            predictions=predictions,
            signals=signals,
            confidence=confidence,
            model_id=self.config.model_id,
        )
        
        self._last_prediction = result
        self._prediction_history.append(result)
        
        return result
    
    def _calculate_confidence(self, predictions: np.ndarray) -> float:
        """Calculate prediction confidence."""
        if len(predictions) == 0:
            return 0.0
        
        pred_std = np.std(predictions)
        pred_range = np.max(predictions) - np.min(predictions)
        
        if pred_range == 0:
            return 0.0
        
        confidence = 1.0 - (pred_std / pred_range)
        return max(0.0, min(1.0, confidence))
    
    def get_signal_for_bar(self, bar_index: int) -> int:
        """Get trading signal for a specific bar."""
        if self._last_prediction is None:
            return SignalType.HOLD.value
        
        if bar_index >= len(self._last_prediction.signals):
            return SignalType.HOLD.value
        
        signal = self._last_prediction.signals[bar_index]
        
        if self._last_prediction.confidence < self.config.min_confidence:
            return SignalType.HOLD.value
        
        return signal
    
    def should_retrain(self, days_since_training: int) -> bool:
        """Check if model should be retrained."""
        return days_since_training >= self.config.retrain_interval_days


class LightGBMStrategy(BaseMLStrategy):
    """
    LightGBM-based trading strategy.
    
    Uses gradient boosting for prediction with configurable
    prediction threshold for signal generation.
    """
    
    def __init__(self, config: MLStrategyConfig):
        super().__init__(config)
        self._threshold = config.prediction_threshold
    
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Generate predictions using LightGBM model."""
        if self._model is None:
            if not self.load_model():
                return np.zeros(len(features))
        
        try:
            if hasattr(self._model, "predict"):
                predictions = self._model.predict(features)
            else:
                predictions = np.zeros(len(features))
            
            return predictions
            
        except Exception as e:
            logger.error(f"[LightGBMStrategy] Prediction error: {e}")
            return np.zeros(len(features))
    
    def generate_signals(self, predictions: np.ndarray) -> List[int]:
        """Convert predictions to signals using threshold."""
        signals = []
        
        for pred in predictions:
            if pred > self._threshold:
                signals.append(SignalType.BUY.value)
            elif pred < -self._threshold:
                signals.append(SignalType.SELL.value)
            else:
                signals.append(SignalType.HOLD.value)
        
        return signals
    
    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        from app.services.qlib.model_loader import get_model_loader, ModelType
        
        loader = get_model_loader()
        model = loader.train_model(
            model_type=ModelType.LIGHTGBM,
            X_train=X_train,
            y_train=y_train,
            params=params,
            model_id=self.config.model_id,
        )
        
        if model is not None:
            self._model = model
            return True
        
        return False


class QlibMLStrategy(BaseMLStrategy):
    """
    Full Qlib integration strategy.
    
    Uses Qlib's model zoo (HIST, GATE, etc.) for prediction
    with Alpha158/Alpha360 features.
    """
    
    def __init__(self, config: MLStrategyConfig, model_class: str = "HIST"):
        super().__init__(config)
        self.model_class = model_class
        self._qlib_initialized = False
    
    def _init_qlib(self) -> bool:
        if self._qlib_initialized:
            return True
        
        from app.services.qlib.qlib_init import QlibInitializer
        
        initializer = QlibInitializer()
        if initializer.init():
            self._qlib_initialized = True
            return True
        
        return False
    
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Generate predictions using Qlib model."""
        if not self._qlib_initialized:
            if not self._init_qlib():
                return np.zeros(len(features))
        
        if self._model is None:
            if not self.load_model():
                return np.zeros(len(features))
        
        try:
            predictions = self._model.predict(features)
            return predictions
            
        except Exception as e:
            logger.error(f"[QlibMLStrategy] Prediction error: {e}")
            return np.zeros(len(features))
    
    def generate_signals(self, predictions: np.ndarray) -> List[int]:
        """Convert predictions to signals using rank-based approach."""
        if len(predictions) == 0:
            return []
        
        signals = []
        
        pred_series = pd.Series(predictions)
        pred_rank = pred_series.rank(pct=True)
        
        for rank in pred_rank:
            if rank > 0.7:
                signals.append(SignalType.BUY.value)
            elif rank < 0.3:
                signals.append(SignalType.SELL.value)
            else:
                signals.append(SignalType.HOLD.value)
        
        return signals


class EnsembleMLStrategy(BaseMLStrategy):
    """
    Ensemble strategy combining multiple ML models.
    
    Aggregates predictions from multiple models using
    configurable voting or averaging methods.
    """
    
    def __init__(
        self,
        config: MLStrategyConfig,
        strategies: List[BaseMLStrategy],
        aggregation: str = "mean",
    ):
        super().__init__(config)
        self.strategies = strategies
        self.aggregation = aggregation
    
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Generate ensemble predictions."""
        all_predictions = []
        
        for strategy in self.strategies:
            pred = strategy.predict(features)
            all_predictions.append(pred)
        
        predictions_array = np.array(all_predictions)
        
        if self.aggregation == "mean":
            return np.mean(predictions_array, axis=0)
        elif self.aggregation == "median":
            return np.median(predictions_array, axis=0)
        elif self.aggregation == "max":
            return np.max(predictions_array, axis=0)
        else:
            return np.mean(predictions_array, axis=0)
    
    def generate_signals(self, predictions: np.ndarray) -> List[int]:
        """Generate signals from ensemble predictions."""
        signals = []
        
        for pred in predictions:
            if pred > self.config.prediction_threshold:
                signals.append(SignalType.BUY.value)
            elif pred < -self.config.prediction_threshold:
                signals.append(SignalType.SELL.value)
            else:
                signals.append(SignalType.HOLD.value)
        
        return signals


def create_ml_strategy(
    model_id: str,
    strategy_type: str = "lightgbm",
    feature_set: str = "Alpha158",
    **kwargs,
) -> BaseMLStrategy:
    """
    Factory function to create ML strategies.
    
    Args:
        model_id: Unique model identifier
        strategy_type: Type of strategy (lightgbm, qlib, ensemble)
        feature_set: Feature set to use (Alpha158, Alpha360)
        **kwargs: Additional configuration options
        
    Returns:
        Configured ML strategy instance
    """
    config = MLStrategyConfig(
        model_id=model_id,
        feature_set=feature_set,
        **kwargs,
    )
    
    if strategy_type == "lightgbm":
        return LightGBMStrategy(config)
    elif strategy_type == "qlib":
        return QlibMLStrategy(config, **kwargs)
    elif strategy_type == "ensemble":
        strategies = kwargs.get("strategies", [])
        aggregation = kwargs.get("aggregation", "mean")
        return EnsembleMLStrategy(config, strategies, aggregation)
    else:
        logger.warning(f"[MLStrategy] Unknown strategy type: {strategy_type}, using LightGBM")
        return LightGBMStrategy(config)