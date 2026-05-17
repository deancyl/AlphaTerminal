"""
Qlib Initialization Module

Handles Qlib initialization with AlphaTerminal's local data infrastructure.
Provides lazy initialization and graceful fallback when Qlib is not available.
"""
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_QLIB_INITIALIZED = False
_QLIB_AVAILABLE = None


def is_qlib_available() -> bool:
    """Check if Qlib is installed and importable."""
    global _QLIB_AVAILABLE
    if _QLIB_AVAILABLE is None:
        try:
            import qlib
            _QLIB_AVAILABLE = True
        except ImportError:
            _QLIB_AVAILABLE = False
            logger.warning("[Qlib] pyqlib not installed. ML features will be disabled.")
    return _QLIB_AVAILABLE


class QlibInitializer:
    """
    Initialize Qlib with AlphaTerminal's local data.
    
    Usage:
        initializer = QlibInitializer()
        initializer.init()
        
        # Or with custom config
        initializer = QlibInitializer(
            provider_uri="~/.qlib/qlib_data/cn_data",
            redis_host="localhost"
        )
        initializer.init()
    """
    
    DEFAULT_PROVIDER_URI = "~/.qlib/qlib_data/cn_data"
    DEFAULT_REGION = "cn"
    
    def __init__(
        self,
        provider_uri: Optional[str] = None,
        region: str = DEFAULT_REGION,
        redis_host: Optional[str] = None,
        redis_port: int = 6379,
        expression_cache: Optional[str] = None,
        dataset_cache: Optional[str] = None,
    ):
        self.provider_uri = provider_uri or self.DEFAULT_PROVIDER_URI
        self.region = region
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.expression_cache = expression_cache
        self.dataset_cache = dataset_cache
        self._initialized = False
    
    def init(self, force: bool = False) -> bool:
        """
        Initialize Qlib.
        
        Args:
            force: Force re-initialization even if already initialized
            
        Returns:
            True if initialization successful, False otherwise
        """
        global _QLIB_INITIALIZED
        
        if _QLIB_INITIALIZED and not force:
            return True
        
        if not is_qlib_available():
            logger.warning("[Qlib] Cannot initialize - pyqlib not installed")
            return False
        
        try:
            import qlib
            from qlib.config import REG_CN
            
            config = {
                "provider_uri": self.provider_uri,
                "region": self.region,
            }
            
            if self.redis_host:
                config["redis"] = {
                    "host": self.redis_host,
                    "port": self.redis_port,
                }
            
            if self.expression_cache:
                config["expression_cache"] = self.expression_cache
            
            if self.dataset_cache:
                config["dataset_cache"] = self.dataset_cache
            
            qlib.init(**config)
            _QLIB_INITIALIZED = True
            self._initialized = True
            
            logger.info(f"[Qlib] Initialized with provider: {self.provider_uri}")
            return True
            
        except Exception as e:
            logger.error(f"[Qlib] Initialization failed: {e}")
            return False
    
    def download_data(self, target_dir: Optional[str] = None) -> bool:
        """
        Download Qlib data if not already present.
        
        Args:
            target_dir: Directory to download data to
            
        Returns:
            True if download successful, False otherwise
        """
        if not is_qlib_available():
            return False
        
        try:
            from qlib.data import simple_data_handler
            import subprocess
            
            target = target_dir or self.provider_uri
            target_path = Path(target).expanduser()
            
            if target_path.exists():
                logger.info(f"[Qlib] Data already exists at {target_path}")
                return True
            
            target_path.mkdir(parents=True, exist_ok=True)
            
            subprocess.run(
                ["python", "-m", "qlib.run.get_data", "qlib_data", "cn", target],
                check=True,
                capture_output=True,
            )
            
            logger.info(f"[Qlib] Data downloaded to {target_path}")
            return True
            
        except Exception as e:
            logger.error(f"[Qlib] Data download failed: {e}")
            return False
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized


def get_qlib_initializer() -> QlibInitializer:
    """Get the default QlibInitializer instance."""
    return QlibInitializer()
