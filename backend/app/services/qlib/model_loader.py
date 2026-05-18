"""
Model Loader for Qlib Integration

Loads and manages Qlib ML models (LightGBM, HIST, GATE, etc.)
with fallback to scikit-learn when Qlib is not available.
"""
import logging
import os
import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ModelType(Enum):
    LIGHTGBM = "LightGBM"
    HIST = "HIST"
    GATE = "GATE"
    GRU = "GRU"
    LSTM = "LSTM"
    MLP = "MLP"
    XGBOOST = "XGBoost"
    CATBOOST = "CatBoost"
    CUSTOM = "Custom"


class ModelProvider(Enum):
    QLIB = "qlib"
    SKLEARN = "sklearn"
    CUSTOM = "custom"


@dataclass
class ModelInfo:
    model_id: str
    model_type: ModelType
    provider: ModelProvider
    feature_set: str
    created_at: datetime
    updated_at: datetime
    metrics: Dict[str, float] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    path: Optional[str] = None
    is_loaded: bool = False


class ModelLoader:
    """
    Load and manage ML models for trading strategies.
    
    Supports:
        - Qlib models: LightGBM, HIST, GATE, GRU, LSTM
        - Scikit-learn models: RandomForest, GradientBoosting
        - Custom models: Any pickle-serializable model
    """
    
    MODEL_DIR = Path("backend/cache/ml_models")
    SUPPORTED_MODELS = {
        ModelType.LIGHTGBM: ["qlib", "lightgbm"],
        ModelType.HIST: ["qlib"],
        ModelType.GATE: ["qlib"],
        ModelType.GRU: ["qlib"],
        ModelType.LSTM: ["qlib"],
        ModelType.MLP: ["sklearn"],
        ModelType.XGBOOST: ["xgboost"],
        ModelType.CATBOOST: ["catboost"],
    }
    
    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = model_dir or self.MODEL_DIR
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_models: Dict[str, Any] = {}
        self._model_info: Dict[str, ModelInfo] = {}
    
    def load_model(
        self,
        model_id: str,
        model_type: ModelType = ModelType.LIGHTGBM,
        provider: ModelProvider = ModelProvider.QLIB,
    ) -> Optional[Any]:
        """
        Load a model by ID.
        
        Args:
            model_id: Unique model identifier
            model_type: Type of model
            provider: Model provider (qlib, sklearn, custom)
            
        Returns:
            Loaded model or None if failed
        """
        if model_id in self._loaded_models:
            return self._loaded_models[model_id]
        
        model_path = self.model_dir / f"{model_id}.pkl"
        
        if not model_path.exists():
            logger.warning(f"[ModelLoader] Model not found: {model_path}")
            return None
        
        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)
            
            self._loaded_models[model_id] = model
            self._model_info[model_id] = ModelInfo(
                model_id=model_id,
                model_type=model_type,
                provider=provider,
                feature_set="unknown",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                path=str(model_path),
                is_loaded=True,
            )
            
            logger.info(f"[ModelLoader] Loaded model: {model_id}")
            return model
            
        except Exception as e:
            logger.error(f"[ModelLoader] Failed to load model {model_id}: {e}")
            return None
    
    def save_model(
        self,
        model: Any,
        model_id: str,
        model_type: ModelType,
        provider: ModelProvider,
        feature_set: str,
        metrics: Optional[Dict[str, float]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Save a model to disk.
        
        Args:
            model: Model object to save
            model_id: Unique model identifier
            model_type: Type of model
            provider: Model provider
            feature_set: Feature set used (Alpha158, Alpha360, etc.)
            metrics: Performance metrics
            params: Model parameters
            
        Returns:
            True if saved successfully
        """
        model_path = self.model_dir / f"{model_id}.pkl"
        
        try:
            with open(model_path, "wb") as f:
                pickle.dump(model, f)
            
            info = ModelInfo(
                model_id=model_id,
                model_type=model_type,
                provider=provider,
                feature_set=feature_set,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metrics=metrics or {},
                params=params or {},
                path=str(model_path),
                is_loaded=True,
            )
            
            self._loaded_models[model_id] = model
            self._model_info[model_id] = info
            
            self._save_model_metadata(model_id, info)
            
            logger.info(f"[ModelLoader] Saved model: {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"[ModelLoader] Failed to save model {model_id}: {e}")
            return False
    
    def predict(
        self,
        model_id: str,
        features: pd.DataFrame,
    ) -> Optional[np.ndarray]:
        """
        Generate predictions using a loaded model.
        
        Args:
            model_id: Model identifier
            features: Feature DataFrame
            
        Returns:
            Prediction array or None if failed
        """
        model = self._loaded_models.get(model_id)
        
        if model is None:
            model = self.load_model(model_id)
            if model is None:
                return None
        
        try:
            if hasattr(model, "predict"):
                predictions = model.predict(features)
            elif hasattr(model, "forward"):
                import torch
                with torch.no_grad():
                    predictions = model.forward(torch.tensor(features.values, dtype=torch.float32))
                    predictions = predictions.numpy()
            else:
                logger.error(f"[ModelLoader] Model {model_id} has no predict method")
                return None
            
            return predictions
            
        except Exception as e:
            logger.error(f"[ModelLoader] Prediction failed for {model_id}: {e}")
            return None
    
    def train_model(
        self,
        model_type: ModelType,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        params: Optional[Dict[str, Any]] = None,
        model_id: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Train a new model.
        
        Args:
            model_type: Type of model to train
            X_train: Training features
            y_train: Training labels
            params: Model parameters
            model_id: Optional model ID (auto-generated if None)
            
        Returns:
            Trained model or None if failed
        """
        model_id = model_id or f"{model_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            if model_type == ModelType.LIGHTGBM:
                import lightgbm as lgb
                
                default_params = {
                    "objective": "regression",
                    "metric": "mse",
                    "boosting_type": "gbdt",
                    "num_leaves": 31,
                    "learning_rate": 0.05,
                    "feature_fraction": 0.8,
                    "verbose": -1,
                }
                train_params = {**default_params, **(params or {})}
                
                train_data = lgb.Dataset(X_train, label=y_train)
                model = lgb.train(train_params, train_data, num_boost_round=100)
                
            elif model_type == ModelType.XGBOOST:
                import xgboost as xgb
                
                default_params = {
                    "objective": "reg:squarederror",
                    "max_depth": 6,
                    "learning_rate": 0.05,
                }
                train_params = {**default_params, **(params or {})}
                
                model = xgb.XGBRegressor(**train_params)
                model.fit(X_train, y_train)
                
            elif model_type == ModelType.MLP:
                from sklearn.neural_network import MLPRegressor
                
                default_params = {
                    "hidden_layer_sizes": (100, 50),
                    "activation": "relu",
                    "max_iter": 500,
                }
                train_params = {**default_params, **(params or {})}
                
                model = MLPRegressor(**train_params)
                model.fit(X_train, y_train)
                
            else:
                logger.error(f"[ModelLoader] Training not implemented for {model_type}")
                return None
            
            self._loaded_models[model_id] = model
            self._model_info[model_id] = ModelInfo(
                model_id=model_id,
                model_type=model_type,
                provider=ModelProvider.SKLEARN if model_type == ModelType.MLP else ModelProvider.CUSTOM,
                feature_set="custom",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                params=params or {},
                is_loaded=True,
            )
            
            logger.info(f"[ModelLoader] Trained model: {model_id}")
            return model
            
        except Exception as e:
            logger.error(f"[ModelLoader] Training failed: {e}")
            return None
    
    def list_models(self) -> List[ModelInfo]:
        """List all available models."""
        models = []
        
        for model_file in self.model_dir.glob("*.pkl"):
            model_id = model_file.stem
            if model_id not in self._model_info:
                info = self._load_model_metadata(model_id)
                if info:
                    self._model_info[model_id] = info
            if model_id in self._model_info:
                models.append(self._model_info[model_id])
        
        return models
    
    def delete_model(self, model_id: str) -> bool:
        """Delete a model."""
        model_path = self.model_dir / f"{model_id}.pkl"
        meta_path = self.model_dir / f"{model_id}_meta.json"
        
        try:
            if model_id in self._loaded_models:
                del self._loaded_models[model_id]
            if model_id in self._model_info:
                del self._model_info[model_id]
            
            if model_path.exists():
                model_path.unlink()
            if meta_path.exists():
                meta_path.unlink()
            
            logger.info(f"[ModelLoader] Deleted model: {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"[ModelLoader] Failed to delete model {model_id}: {e}")
            return False
    
    def _save_model_metadata(self, model_id: str, info: ModelInfo):
        """Save model metadata to JSON."""
        meta_path = self.model_dir / f"{model_id}_meta.json"
        
        try:
            meta = {
                "model_id": info.model_id,
                "model_type": info.model_type.value,
                "provider": info.provider.value,
                "feature_set": info.feature_set,
                "created_at": info.created_at.isoformat(),
                "updated_at": info.updated_at.isoformat(),
                "metrics": info.metrics,
                "params": info.params,
            }
            
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
                
        except Exception as e:
            logger.warning(f"[ModelLoader] Failed to save metadata: {e}")
    
    def _load_model_metadata(self, model_id: str) -> Optional[ModelInfo]:
        """Load model metadata from JSON."""
        meta_path = self.model_dir / f"{model_id}_meta.json"
        
        if not meta_path.exists():
            return None
        
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
            
            return ModelInfo(
                model_id=meta["model_id"],
                model_type=ModelType(meta["model_type"]),
                provider=ModelProvider(meta["provider"]),
                feature_set=meta["feature_set"],
                created_at=datetime.fromisoformat(meta["created_at"]),
                updated_at=datetime.fromisoformat(meta["updated_at"]),
                metrics=meta.get("metrics", {}),
                params=meta.get("params", {}),
            )
            
        except Exception as e:
            logger.warning(f"[ModelLoader] Failed to load metadata: {e}")
            return None


def get_model_loader() -> ModelLoader:
    """Get the default ModelLoader instance."""
    return ModelLoader()