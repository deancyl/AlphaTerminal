"""
Market Regime Detector Service

Detects market states (bull, bear, sideways, high volatility) using multiple indicators.

Debug Cycles:
1. Input validation
2. Trend regime detection (MA trends, ADX)
3. Volatility regime detection (ATR)
4. Momentum regime detection (RSI)
5. Overall regime classification
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RegimeResult:
    """
    Market regime detection result
    
    Attributes:
        trend_regime: 'bull', 'bear', or 'sideways'
        volatility_regime: 'high', 'medium', or 'low'
        momentum_regime: 'strong', 'weak', or 'neutral'
        overall_regime: Combined regime classification
        confidence: Confidence score (0.0 to 1.0)
        indicators: Dictionary of indicator values used
        timestamp: Detection timestamp
    """
    trend_regime: str
    volatility_regime: str
    momentum_regime: str
    overall_regime: str
    confidence: float
    indicators: Dict[str, float] = field(default_factory=dict)
    timestamp: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "trend_regime": self.trend_regime,
            "volatility_regime": self.volatility_regime,
            "momentum_regime": self.momentum_regime,
            "overall_regime": self.overall_regime,
            "confidence": self.confidence,
            "indicators": self.indicators,
            "timestamp": self.timestamp
        }


class MarketRegimeDetector:
    """
    Market Regime Detector with 5 debug cycles
    
    Detects market states using:
    - Moving average trends (SMA 20/50/200)
    - ADX for trend strength
    - ATR for volatility
    - RSI for momentum
    
    Debug Cycles:
    1. Input validation - validate price data
    2. Trend regime detection - MA crossovers, ADX
    3. Volatility regime detection - ATR percentiles
    4. Momentum regime detection - RSI levels
    5. Overall regime classification - combine all signals
    """
    
    # Regime thresholds
    TREND_BULL_THRESHOLD = 0.02  # 2% above MA
    TREND_BEAR_THRESHOLD = -0.02  # 2% below MA
    ADX_STRONG_THRESHOLD = 25  # Strong trend
    ADX_WEAK_THRESHOLD = 20  # Weak/no trend
    
    VOLATILITY_HIGH_PERCENTILE = 80  # Top 20%
    VOLATILITY_LOW_PERCENTILE = 20  # Bottom 20%
    
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    
    MIN_DATA_POINTS = 50  # Minimum data points required
    
    def __init__(self, lookback_short: int = 20, lookback_medium: int = 50, 
                 lookback_long: int = 200, atr_period: int = 14, 
                 rsi_period: int = 14, adx_period: int = 14):
        """
        Initialize MarketRegimeDetector
        
        Args:
            lookback_short: Short-term MA period (default: 20)
            lookback_medium: Medium-term MA period (default: 50)
            lookback_long: Long-term MA period (default: 200)
            atr_period: ATR calculation period (default: 14)
            rsi_period: RSI calculation period (default: 14)
            adx_period: ADX calculation period (default: 14)
        """
        self.lookback_short = lookback_short
        self.lookback_medium = lookback_medium
        self.lookback_long = lookback_long
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        
        logger.debug(
            f"[Cycle 0] MarketRegimeDetector initialized - "
            f"MA periods: ({lookback_short}, {lookback_medium}, {lookback_long}), "
            f"ATR: {atr_period}, RSI: {rsi_period}, ADX: {adx_period}"
        )
    
    # ==================== Cycle 1: Input Validation ====================
    
    def _validate_inputs(self, prices: pd.Series, lookback: int) -> Tuple[bool, str, pd.Series]:
        """
        Debug Cycle 1: Input validation
        
        Args:
            prices: Series of price values (close prices)
            lookback: Required lookback period
            
        Returns:
            Tuple of (is_valid, error_message, cleaned_prices)
        """
        logger.debug("[Cycle 1 - Input Validation] Starting input validation")
        
        # Check if prices is None or empty
        if prices is None or len(prices) == 0:
            error_msg = "Price series is empty or None"
            logger.error(f"[Cycle 1] {error_msg}")
            return False, error_msg, pd.Series(dtype=float)
        
        # Check minimum data points
        min_required = max(lookback, self.MIN_DATA_POINTS)
        if len(prices) < min_required:
            error_msg = f"Insufficient data points: {len(prices)} < {min_required}"
            logger.error(f"[Cycle 1] {error_msg}")
            return False, error_msg, pd.Series(dtype=float)
        
        # Check for NaN values
        nan_count = prices.isna().sum()
        if nan_count > 0:
            logger.warning(f"[Cycle 1] Found {nan_count} NaN values, will be dropped")
        
        # Clean prices
        prices_clean = prices.dropna()
        
        if len(prices_clean) < min_required:
            error_msg = f"Insufficient data after cleaning: {len(prices_clean)} < {min_required}"
            logger.error(f"[Cycle 1] {error_msg}")
            return False, error_msg, pd.Series(dtype=float)
        
        # Check for infinite values
        if np.isinf(prices_clean).any():
            inf_count = np.isinf(prices_clean).sum()
            error_msg = f"Price series contains {inf_count} infinite values"
            logger.error(f"[Cycle 1] {error_msg}")
            return False, error_msg, pd.Series(dtype=float)
        
        # Check for negative or zero prices
        if (prices_clean <= 0).any():
            neg_count = (prices_clean <= 0).sum()
            logger.warning(f"[Cycle 1] Found {neg_count} non-positive prices")
        
        # Check price variance (avoid constant prices)
        if prices_clean.std() == 0:
            error_msg = "Price series has zero variance (constant prices)"
            logger.error(f"[Cycle 1] {error_msg}")
            return False, error_msg, pd.Series(dtype=float)
        
        logger.debug(
            f"[Cycle 1] Input validation passed - "
            f"valid_prices={len(prices_clean)}, "
            f"min={prices_clean.min():.2f}, max={prices_clean.max():.2f}, "
            f"mean={prices_clean.mean():.2f}"
        )
        
        return True, "", prices_clean
    
    # ==================== Cycle 2: Trend Regime Detection ====================
    
    def detect_trend_regime(self, prices: pd.Series) -> str:
        """
        Debug Cycle 2: Trend regime detection
        
        Detects trend regime using:
        - Moving average crossovers (SMA 20/50/200)
        - Price position relative to MAs
        - ADX for trend strength
        
        Args:
            prices: Series of price values
            
        Returns:
            'bull', 'bear', or 'sideways'
        """
        logger.debug("[Cycle 2 - Trend Regime] Starting trend regime detection")
        
        # Calculate moving averages
        sma_short = prices.rolling(window=self.lookback_short).mean()
        sma_medium = prices.rolling(window=self.lookback_medium).mean()
        sma_long = prices.rolling(window=self.lookback_long).mean()
        
        # Get latest values
        current_price = prices.iloc[-1]
        current_sma_short = sma_short.iloc[-1]
        current_sma_medium = sma_medium.iloc[-1]
        current_sma_long = sma_long.iloc[-1]
        
        logger.debug(
            f"[Cycle 2] MA values - "
            f"Price: {current_price:.2f}, "
            f"SMA{self.lookback_short}: {current_sma_short:.2f}, "
            f"SMA{self.lookback_medium}: {current_sma_medium:.2f}, "
            f"SMA{self.lookback_long}: {current_sma_long:.2f}"
        )
        
        # Calculate price position relative to MAs
        price_vs_short = (current_price - current_sma_short) / current_sma_short
        price_vs_medium = (current_price - current_sma_medium) / current_sma_medium
        price_vs_long = (current_price - current_sma_long) / current_sma_long
        
        logger.debug(
            f"[Cycle 2] Price vs MA - "
            f"vs SMA{self.lookback_short}: {price_vs_short*100:.2f}%, "
            f"vs SMA{self.lookback_medium}: {price_vs_medium*100:.2f}%, "
            f"vs SMA{self.lookback_long}: {price_vs_long*100:.2f}%"
        )
        
        # Calculate ADX for trend strength
        adx = self._calculate_adx(prices)
        logger.debug(f"[Cycle 2] ADX value: {adx:.2f}")
        
        # Determine trend regime
        bull_signals = 0
        bear_signals = 0
        
        # Price above MAs
        if price_vs_short > self.TREND_BULL_THRESHOLD:
            bull_signals += 1
        elif price_vs_short < self.TREND_BEAR_THRESHOLD:
            bear_signals += 1
        
        if price_vs_medium > self.TREND_BULL_THRESHOLD:
            bull_signals += 1
        elif price_vs_medium < self.TREND_BEAR_THRESHOLD:
            bear_signals += 1
        
        if price_vs_long > self.TREND_BULL_THRESHOLD:
            bull_signals += 1
        elif price_vs_long < self.TREND_BEAR_THRESHOLD:
            bear_signals += 1
        
        # MA alignment (golden cross / death cross)
        if current_sma_short > current_sma_medium > current_sma_long:
            bull_signals += 2  # Strong bullish alignment
            logger.debug("[Cycle 2] Golden cross detected (bullish MA alignment)")
        elif current_sma_short < current_sma_medium < current_sma_long:
            bear_signals += 2  # Strong bearish alignment
            logger.debug("[Cycle 2] Death cross detected (bearish MA alignment)")
        
        # ADX confirmation
        if adx > self.ADX_STRONG_THRESHOLD:
            # Strong trend - amplify signals
            if bull_signals > bear_signals:
                bull_signals += 1
            elif bear_signals > bull_signals:
                bear_signals += 1
            logger.debug(f"[Cycle 2] Strong trend confirmed by ADX ({adx:.2f} > {self.ADX_STRONG_THRESHOLD})")
        elif adx < self.ADX_WEAK_THRESHOLD:
            # Weak trend - reduce confidence
            bull_signals = max(0, bull_signals - 1)
            bear_signals = max(0, bear_signals - 1)
            logger.debug(f"[Cycle 2] Weak trend indicated by ADX ({adx:.2f} < {self.ADX_WEAK_THRESHOLD})")
        
        # Determine final regime
        if bull_signals >= 3 and bull_signals > bear_signals + 1:
            regime = "bull"
        elif bear_signals >= 3 and bear_signals > bull_signals + 1:
            regime = "bear"
        else:
            regime = "sideways"
        
        logger.debug(
            f"[Cycle 2] Trend regime determined: {regime} "
            f"(bull_signals={bull_signals}, bear_signals={bear_signals})"
        )
        
        return regime
    
    def _calculate_adx(self, prices: pd.Series) -> float:
        """
        Calculate Average Directional Index (ADX)
        
        ADX measures trend strength regardless of direction.
        Values: 0-100
        - < 20: Weak/no trend
        - 20-25: Developing trend
        - > 25: Strong trend
        - > 50: Very strong trend
        
        Args:
            prices: Series of price values
            
        Returns:
            ADX value (float)
        """
        # Need high, low, close for proper ADX
        # For simplicity, use close prices and estimate
        # In production, use full OHLC data
        
        # Calculate price changes
        delta = prices.diff()
        
        # Simplified ADX using price momentum
        # Calculate directional movement
        plus_dm = delta.where(delta > 0, 0)
        minus_dm = (-delta).where(delta < 0, 0)
        
        # Calculate true range (simplified)
        tr = prices.diff().abs()
        
        # Smooth the values
        smooth_plus_dm = plus_dm.rolling(window=self.adx_period).mean()
        smooth_minus_dm = minus_dm.rolling(window=self.adx_period).mean()
        smooth_tr = tr.rolling(window=self.adx_period).mean()
        
        # Calculate directional indicators
        plus_di = 100 * (smooth_plus_dm / smooth_tr)
        minus_di = 100 * (smooth_minus_dm / smooth_tr)
        
        # Calculate DX
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 0.0001)
        
        # Calculate ADX
        adx = dx.rolling(window=self.adx_period).mean()
        
        return float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0.0
    
    # ==================== Cycle 3: Volatility Regime Detection ====================
    
    def detect_volatility_regime(self, returns: pd.Series) -> str:
        """
        Debug Cycle 3: Volatility regime detection
        
        Detects volatility regime using:
        - ATR (Average True Range) percentiles
        - Historical volatility comparison
        
        Args:
            returns: Series of daily returns
            
        Returns:
            'high', 'medium', or 'low'
        """
        logger.debug("[Cycle 3 - Volatility Regime] Starting volatility regime detection")
        
        # Calculate rolling volatility (standard deviation of returns)
        vol_short = returns.rolling(window=20).std() * np.sqrt(252)  # Annualized
        vol_medium = returns.rolling(window=60).std() * np.sqrt(252)
        
        # Current volatility
        current_vol = vol_short.iloc[-1]
        
        logger.debug(
            f"[Cycle 3] Volatility values - "
            f"Current (20d): {current_vol*100:.2f}%, "
            f"Medium (60d): {vol_medium.iloc[-1]*100:.2f}%"
        )
        
        # Calculate historical volatility percentiles
        vol_series = vol_short.dropna()
        
        if len(vol_series) < 20:
            logger.warning("[Cycle 3] Insufficient volatility history, defaulting to medium")
            return "medium"
        
        # Calculate percentiles
        vol_percentile = (vol_series <= current_vol).sum() / len(vol_series) * 100
        
        logger.debug(
            f"[Cycle 3] Volatility percentile: {vol_percentile:.1f}% "
            f"(current={current_vol*100:.2f}%, "
            f"median={vol_series.median()*100:.2f}%, "
            f"max={vol_series.max()*100:.2f}%, "
            f"min={vol_series.min()*100:.2f}%)"
        )
        
        # Determine volatility regime
        if vol_percentile >= self.VOLATILITY_HIGH_PERCENTILE:
            regime = "high"
        elif vol_percentile <= self.VOLATILITY_LOW_PERCENTILE:
            regime = "low"
        else:
            regime = "medium"
        
        # Additional check: recent volatility spike
        recent_vol = returns.tail(5).std() * np.sqrt(252)
        if recent_vol > current_vol * 1.5:
            logger.debug(f"[Cycle 3] Recent volatility spike detected: {recent_vol*100:.2f}%")
            if regime == "low":
                regime = "medium"
            elif regime == "medium":
                regime = "high"
        
        logger.debug(f"[Cycle 3] Volatility regime determined: {regime}")
        
        return regime
    
    def calculate_atr(self, prices: pd.Series, period: int = 14) -> float:
        """
        Calculate Average True Range (ATR)
        
        ATR measures market volatility.
        
        Args:
            prices: Series of price values
            period: ATR period (default: 14)
            
        Returns:
            ATR value (float)
        """
        # Calculate True Range (simplified using close prices)
        # TR = max(H-L, |H-C_prev|, |L-C_prev|)
        # Simplified: TR = |Close - Close_prev|
        tr = prices.diff().abs()
        
        # Calculate ATR (smoothed TR)
        atr = tr.rolling(window=period).mean()
        
        return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
    
    # ==================== Cycle 4: Momentum Regime Detection ====================
    
    def detect_momentum_regime(self, prices: pd.Series) -> str:
        """
        Debug Cycle 4: Momentum regime detection
        
        Detects momentum regime using:
        - RSI (Relative Strength Index)
        - Price rate of change
        
        Args:
            prices: Series of price values
            
        Returns:
            'strong', 'weak', or 'neutral'
        """
        logger.debug("[Cycle 4 - Momentum Regime] Starting momentum regime detection")
        
        # Calculate RSI
        rsi = self._calculate_rsi(prices)
        
        logger.debug(f"[Cycle 4] RSI value: {rsi:.2f}")
        
        # Calculate rate of change (ROC)
        roc_periods = [5, 10, 20]
        roc_values = []
        
        for period in roc_periods:
            if len(prices) > period:
                roc = (prices.iloc[-1] - prices.iloc[-period-1]) / prices.iloc[-period-1] * 100
                roc_values.append(roc)
                logger.debug(f"[Cycle 4] ROC({period}): {roc:.2f}%")
        
        # Determine momentum regime
        strong_signals = 0
        weak_signals = 0
        
        # RSI analysis
        if rsi > self.RSI_OVERBOUGHT:
            strong_signals += 2  # Strong bullish momentum
            logger.debug(f"[Cycle 4] RSI overbought ({rsi:.2f} > {self.RSI_OVERBOUGHT})")
        elif rsi < self.RSI_OVERSOLD:
            strong_signals += 2  # Strong bearish momentum (oversold = potential reversal)
            logger.debug(f"[Cycle 4] RSI oversold ({rsi:.2f} < {self.RSI_OVERSOLD})")
        elif 40 <= rsi <= 60:
            weak_signals += 1  # Neutral zone
            logger.debug(f"[Cycle 4] RSI in neutral zone ({rsi:.2f})")
        
        # ROC analysis
        if roc_values:
            avg_roc = np.mean(roc_values)
            if abs(avg_roc) > 5:  # > 5% average ROC
                strong_signals += 1
                logger.debug(f"[Cycle 4] Strong ROC detected: {avg_roc:.2f}%")
            elif abs(avg_roc) < 1:  # < 1% average ROC
                weak_signals += 1
                logger.debug(f"[Cycle 4] Weak ROC detected: {avg_roc:.2f}%")
        
        # Determine momentum regime
        if strong_signals >= 2:
            regime = "strong"
        elif weak_signals >= 2:
            regime = "weak"
        else:
            regime = "neutral"
        
        logger.debug(
            f"[Cycle 4] Momentum regime determined: {regime} "
            f"(strong_signals={strong_signals}, weak_signals={weak_signals})"
        )
        
        return regime
    
    def _calculate_rsi(self, prices: pd.Series) -> float:
        """
        Calculate Relative Strength Index (RSI)
        
        RSI measures momentum and overbought/oversold conditions.
        Values: 0-100
        - > 70: Overbought
        - < 30: Oversold
        - 40-60: Neutral
        
        Args:
            prices: Series of price values
            
        Returns:
            RSI value (float)
        """
        # Calculate price changes
        delta = prices.diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0)
        losses = (-delta).where(delta < 0, 0)
        
        # Calculate average gains and losses
        avg_gains = gains.rolling(window=self.rsi_period).mean()
        avg_losses = losses.rolling(window=self.rsi_period).mean()
        
        # Calculate RS (Relative Strength)
        rs = avg_gains / (avg_losses + 0.0001)  # Avoid division by zero
        
        # Calculate RSI
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
    
    # ==================== Cycle 5: Overall Regime Classification ====================
    
    def detect_regime(self, prices: pd.Series, lookback: int = 252) -> RegimeResult:
        """
        Debug Cycle 5: Overall regime classification
        
        Combines all regime signals to determine overall market regime.
        
        Args:
            prices: Series of price values
            lookback: Lookback period for analysis (default: 252 = 1 year)
            
        Returns:
            RegimeResult with all regime classifications
        """
        logger.debug("[Cycle 5 - Overall Regime] Starting overall regime classification")
        
        # Cycle 1: Input validation
        is_valid, error_msg, prices_clean = self._validate_inputs(prices, lookback)
        
        if not is_valid:
            logger.error(f"[Cycle 5] Input validation failed: {error_msg}")
            return self._empty_result(error_msg)
        
        # Use cleaned prices
        prices = prices_clean
        
        # Calculate returns for volatility analysis
        returns = prices.pct_change().dropna()
        
        if len(returns) < 20:
            error_msg = f"Insufficient returns data: {len(returns)} < 20"
            logger.error(f"[Cycle 5] {error_msg}")
            return self._empty_result(error_msg)
        
        # Cycle 2: Trend regime detection
        trend_regime = self.detect_trend_regime(prices)
        
        # Cycle 3: Volatility regime detection
        volatility_regime = self.detect_volatility_regime(returns)
        
        # Cycle 4: Momentum regime detection
        momentum_regime = self.detect_momentum_regime(prices)
        
        # Calculate indicators for result
        indicators = self._calculate_all_indicators(prices, returns)
        
        # Cycle 5: Overall regime classification
        overall_regime, confidence = self._classify_overall_regime(
            trend_regime, volatility_regime, momentum_regime, indicators
        )
        
        # Create result
        result = RegimeResult(
            trend_regime=trend_regime,
            volatility_regime=volatility_regime,
            momentum_regime=momentum_regime,
            overall_regime=overall_regime,
            confidence=confidence,
            indicators=indicators,
            timestamp=pd.Timestamp.now().isoformat()
        )
        
        logger.debug(
            f"[Cycle 5] Overall regime determined: {overall_regime} "
            f"(trend={trend_regime}, vol={volatility_regime}, "
            f"momentum={momentum_regime}, confidence={confidence:.2f})"
        )
        
        return result
    
    def _calculate_all_indicators(self, prices: pd.Series, returns: pd.Series) -> Dict[str, float]:
        """
        Calculate all technical indicators
        
        Args:
            prices: Series of price values
            returns: Series of daily returns
            
        Returns:
            Dictionary of indicator values
        """
        # Moving averages
        sma_20 = prices.rolling(window=20).mean().iloc[-1]
        sma_50 = prices.rolling(window=50).mean().iloc[-1]
        sma_200 = prices.rolling(window=200).mean().iloc[-1] if len(prices) >= 200 else prices.mean()
        
        current_price = prices.iloc[-1]
        
        # RSI
        rsi = self._calculate_rsi(prices)
        
        # ADX
        adx = self._calculate_adx(prices)
        
        # ATR
        atr = self.calculate_atr(prices)
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
        
        # Volatility (annualized)
        volatility = returns.std() * np.sqrt(252)
        
        # Price momentum
        roc_5 = (current_price - prices.iloc[-6]) / prices.iloc[-6] * 100 if len(prices) > 5 else 0
        roc_20 = (current_price - prices.iloc[-21]) / prices.iloc[-21] * 100 if len(prices) > 20 else 0
        
        return {
            "price": float(current_price),
            "sma_20": float(sma_20),
            "sma_50": float(sma_50),
            "sma_200": float(sma_200),
            "price_vs_sma20_pct": float((current_price - sma_20) / sma_20 * 100),
            "price_vs_sma50_pct": float((current_price - sma_50) / sma_50 * 100),
            "price_vs_sma200_pct": float((current_price - sma_200) / sma_200 * 100),
            "rsi": float(rsi),
            "adx": float(adx),
            "atr": float(atr),
            "atr_pct": float(atr_pct),
            "volatility_annual": float(volatility),
            "roc_5d_pct": float(roc_5),
            "roc_20d_pct": float(roc_20)
        }
    
    def _classify_overall_regime(
        self, 
        trend_regime: str, 
        volatility_regime: str, 
        momentum_regime: str,
        indicators: Dict[str, float]
    ) -> Tuple[str, float]:
        """
        Classify overall market regime
        
        Args:
            trend_regime: Trend regime ('bull', 'bear', 'sideways')
            volatility_regime: Volatility regime ('high', 'medium', 'low')
            momentum_regime: Momentum regime ('strong', 'weak', 'neutral')
            indicators: Dictionary of indicator values
            
        Returns:
            Tuple of (overall_regime, confidence)
        """
        logger.debug("[Cycle 5] Classifying overall regime")
        
        # Score-based classification
        bull_score = 0
        bear_score = 0
        total_weight = 0
        
        # Trend regime (weight: 40%)
        trend_weight = 0.4
        if trend_regime == "bull":
            bull_score += trend_weight * 1.0
        elif trend_regime == "bear":
            bear_score += trend_weight * 1.0
        else:
            # Sideways - split
            bull_score += trend_weight * 0.3
            bear_score += trend_weight * 0.3
        total_weight += trend_weight
        
        # Volatility regime (weight: 20%)
        vol_weight = 0.2
        if volatility_regime == "high":
            # High volatility increases uncertainty
            bull_score += vol_weight * 0.3
            bear_score += vol_weight * 0.3
        elif volatility_regime == "low":
            # Low volatility favors current trend
            if trend_regime == "bull":
                bull_score += vol_weight * 0.5
            elif trend_regime == "bear":
                bear_score += vol_weight * 0.5
        total_weight += vol_weight
        
        # Momentum regime (weight: 30%)
        momentum_weight = 0.3
        if momentum_regime == "strong":
            if trend_regime == "bull":
                bull_score += momentum_weight * 1.0
            elif trend_regime == "bear":
                bear_score += momentum_weight * 1.0
            else:
                # Strong momentum in sideways = potential breakout
                bull_score += momentum_weight * 0.4
                bear_score += momentum_weight * 0.4
        elif momentum_regime == "weak":
            # Weak momentum = trend exhaustion
            bull_score += momentum_weight * 0.2
            bear_score += momentum_weight * 0.2
        total_weight += momentum_weight
        
        # ADX confirmation (weight: 10%)
        adx_weight = 0.1
        adx = indicators.get("adx", 0)
        if adx > self.ADX_STRONG_THRESHOLD:
            # Strong trend - amplify current regime
            if bull_score > bear_score:
                bull_score += adx_weight * 0.5
            else:
                bear_score += adx_weight * 0.5
        total_weight += adx_weight
        
        # Normalize scores
        bull_score /= total_weight
        bear_score /= total_weight
        
        # Determine overall regime
        if bull_score > bear_score + 0.15:
            overall_regime = "bull"
        elif bear_score > bull_score + 0.15:
            overall_regime = "bear"
        else:
            overall_regime = "sideways"
        
        # Calculate confidence
        if overall_regime == "bull":
            confidence = min(1.0, bull_score)
        elif overall_regime == "bear":
            confidence = min(1.0, bear_score)
        else:
            # Sideways confidence is inverse of trend strength
            confidence = 1.0 - abs(bull_score - bear_score)
        
        # Adjust confidence based on regime agreement
        regime_agreement = self._calculate_regime_agreement(
            trend_regime, volatility_regime, momentum_regime, overall_regime
        )
        confidence *= regime_agreement
        
        logger.debug(
            f"[Cycle 5] Classification scores - "
            f"bull={bull_score:.3f}, bear={bear_score:.3f}, "
            f"regime_agreement={regime_agreement:.2f}"
        )
        
        return overall_regime, confidence
    
    def _calculate_regime_agreement(
        self, 
        trend_regime: str, 
        volatility_regime: str, 
        momentum_regime: str,
        overall_regime: str
    ) -> float:
        """
        Calculate regime agreement factor
        
        Higher agreement = higher confidence
        
        Args:
            trend_regime: Trend regime
            volatility_regime: Volatility regime
            momentum_regime: Momentum regime
            overall_regime: Overall regime
            
        Returns:
            Agreement factor (0.5 to 1.0)
        """
        agreement = 1.0
        
        # Check trend-momentum agreement
        if overall_regime in ["bull", "bear"]:
            if trend_regime != overall_regime:
                agreement *= 0.7
            if momentum_regime == "weak":
                agreement *= 0.8
            if volatility_regime == "high":
                agreement *= 0.85
        
        # Sideways should have weak/neutral momentum
        if overall_regime == "sideways":
            if momentum_regime == "strong":
                agreement *= 0.7
        
        return max(0.5, agreement)
    
    def get_regime_score(self, prices: pd.Series) -> float:
        """
        Get numerical regime score (-1 to 1)
        
        -1: Strong bear market
         0: Sideways/neutral
        +1: Strong bull market
        
        Args:
            prices: Series of price values
            
        Returns:
            Regime score (float between -1 and 1)
        """
        logger.debug("[Regime Score] Calculating regime score")
        
        result = self.detect_regime(prices)
        
        # Base score from overall regime
        if result.overall_regime == "bull":
            base_score = 0.5
        elif result.overall_regime == "bear":
            base_score = -0.5
        else:
            base_score = 0.0
        
        # Adjust by confidence
        score = base_score * result.confidence
        
        # Additional adjustment by indicators
        indicators = result.indicators
        
        # RSI adjustment
        rsi = indicators.get("rsi", 50)
        if rsi > 70:
            score += 0.1  # Strong momentum
        elif rsi < 30:
            score -= 0.1  # Weak momentum
        
        # ADX adjustment
        adx = indicators.get("adx", 0)
        if adx > 25:
            score *= 1.1  # Amplify strong trends
        
        # Clamp to [-1, 1]
        score = max(-1.0, min(1.0, score))
        
        logger.debug(f"[Regime Score] Final score: {score:.3f}")
        
        return score
    
    def _empty_result(self, error_msg: str) -> RegimeResult:
        """
        Return empty result with error
        
        Args:
            error_msg: Error message
            
        Returns:
            Empty RegimeResult
        """
        return RegimeResult(
            trend_regime="unknown",
            volatility_regime="unknown",
            momentum_regime="unknown",
            overall_regime="unknown",
            confidence=0.0,
            indicators={"error": error_msg},
            timestamp=pd.Timestamp.now().isoformat()
        )
    
    # ==================== Utility Methods ====================
    
    def get_regime_description(self, regime: str) -> str:
        """
        Get human-readable regime description
        
        Args:
            regime: Regime string
            
        Returns:
            Description string
        """
        descriptions = {
            "bull": "Bull market - prices trending upward with strong momentum",
            "bear": "Bear market - prices trending downward with weak momentum",
            "sideways": "Sideways market - prices range-bound with neutral momentum",
            "high": "High volatility - significant price fluctuations expected",
            "medium": "Medium volatility - normal market conditions",
            "low": "Low volatility - stable price movements",
            "strong": "Strong momentum - significant price movement in trend direction",
            "weak": "Weak momentum - minimal price movement, potential trend exhaustion",
            "neutral": "Neutral momentum - balanced buying and selling pressure",
            "unknown": "Unknown regime - insufficient data or error"
        }
        return descriptions.get(regime, f"Unknown regime: {regime}")
    
    def analyze_regime_transitions(self, prices: pd.Series, window: int = 63) -> List[Dict[str, Any]]:
        """
        Analyze regime transitions over time
        
        Args:
            prices: Series of price values
            window: Rolling window for analysis (default: 63 = 3 months)
            
        Returns:
            List of regime snapshots over time
        """
        logger.debug(f"[Regime Transitions] Analyzing transitions with window={window}")
        
        if len(prices) < window + self.MIN_DATA_POINTS:
            logger.warning("[Regime Transitions] Insufficient data for transition analysis")
            return []
        
        transitions = []
        
        # Analyze regime at each window
        for i in range(window, len(prices), window // 2):  # Overlap for smoother analysis
            window_prices = prices.iloc[:i]
            
            if len(window_prices) < self.MIN_DATA_POINTS:
                continue
            
            result = self.detect_regime(window_prices)
            
            transitions.append({
                "date": prices.index[i-1].isoformat() if hasattr(prices.index[i-1], 'isoformat') else str(prices.index[i-1]),
                "overall_regime": result.overall_regime,
                "trend_regime": result.trend_regime,
                "volatility_regime": result.volatility_regime,
                "momentum_regime": result.momentum_regime,
                "confidence": result.confidence,
                "price": float(prices.iloc[i-1])
            })
        
        logger.debug(f"[Regime Transitions] Analyzed {len(transitions)} regime snapshots")
        
        return transitions
