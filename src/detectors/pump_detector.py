"""
PUMP detection logic
"""

import numpy as np
from typing import Dict, List
from loguru import logger


class PumpDetector:
    """Detects pump events using multi-factor scoring"""
    
    def __init__(self, config: dict):
        """
        Initialize PUMP detector
        
        Args:
            config: Detection configuration from config.yaml
        """
        self.config = config['pump']
        self.enabled = self.config.get('enabled', True)
        
        # Factor weights
        self.weights = self.config['weights']
        
        # Factor thresholds
        self.thresholds = self.config['thresholds']
        
        # Mandatory conditions
        self.mandatory = self.config['mandatory']
        
        # Confidence threshold
        self.confidence_threshold = self.config['confidence_threshold']
        
        logger.info(f"PumpDetector initialized (threshold: {self.confidence_threshold})")
    
    def detect(self, factors: Dict[str, float]) -> Dict:
        """
        Detect PUMP event
        
        Args:
            factors: Dict of calculated factors
            
        Returns:
            Detection result dict:
            {
                'is_pump': bool,
                'confidence': float,
                'trigger_factors': list,
                'risk_level': str
            }
        """
        if not self.enabled:
            return self._empty_result()
        
        try:
            # Check mandatory conditions first
            if not self._check_mandatory_conditions(factors):
                return self._empty_result()
            
            # Calculate individual factor scores
            factor_scores = []
            trigger_factors = []
            
            for factor_name, weight in self.weights.items():
                factor_value = factors.get(factor_name, 0)
                threshold = self.thresholds.get(factor_name, 0)
                
                # Calculate score for this factor
                score = self._score_factor(factor_name, factor_value, threshold)
                
                # Weighted score
                weighted_score = score * weight
                factor_scores.append(weighted_score)
                
                # Record if significantly triggered
                if score > 0.6:
                    trigger_factors.append({
                        'name': factor_name,
                        'value': float(factor_value),
                        'threshold': float(threshold),
                        'score': float(score),
                        'weight': float(weight)
                    })
            
            # Calculate total confidence score
            total_score = sum(factor_scores)
            
            # Determine if PUMP
            is_pump = total_score >= self.confidence_threshold
            
            # Determine risk level
            risk_level = self._determine_risk_level(total_score)
            
            result = {
                'is_pump': is_pump,
                'confidence': float(total_score),
                'trigger_factors': trigger_factors,
                'risk_level': risk_level,
                'factor_scores': {name: float(score) for name, score in zip(self.weights.keys(), factor_scores)}
            }
            
            if is_pump:
                logger.warning(f"?? PUMP DETECTED! Confidence: {total_score:.2%}, Risk: {risk_level}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error in PUMP detection: {e}")
            return self._empty_result()
    
    def _check_mandatory_conditions(self, factors: Dict[str, float]) -> bool:
        """
        Check mandatory conditions that must be met
        
        Args:
            factors: Factor values
            
        Returns:
            True if all mandatory conditions are met
        """
        # Must have price increase
        price_velocity = factors.get('price_velocity_5m', 0)
        min_price_change = self.mandatory.get('min_price_change', 5.0)
        
        if price_velocity < min_price_change:
            return False
        
        # Must have volume spike
        volume_spike_score = factors.get('volume_spike_score', 0)
        min_volume_spike = self.mandatory.get('min_volume_spike', 0.4)
        
        if volume_spike_score < min_volume_spike:
            return False
        
        return True
    
    def _score_factor(self, factor_name: str, value: float, threshold: float) -> float:
        """
        Calculate score for individual factor
        
        Args:
            factor_name: Name of the factor
            value: Current value
            threshold: Threshold value
            
        Returns:
            Score between 0-1
        """
        if factor_name == 'price_velocity_5m':
            return self._score_price_velocity(value, threshold)
        
        elif factor_name == 'volume_spike_score':
            return min(value, 1.0)  # Already 0-1
        
        elif factor_name == 'buy_sell_ratio':
            return self._score_ratio(value, threshold)
        
        elif factor_name == 'bid_ask_imbalance':
            return self._score_imbalance(value, threshold)
        
        elif factor_name == 'trade_intensity':
            return self._score_intensity(value, threshold)
        
        else:
            # Generic scoring
            if value >= threshold:
                return min((value / threshold - 1) / 2 + 0.5, 1.0)
            return 0.0
    
    def _score_price_velocity(self, value: float, threshold: float) -> float:
        """Score price velocity using sigmoid function"""
        if value < 0:
            return 0.0
        
        # Normalize
        normalized = value / threshold
        
        # Sigmoid: smooth transition around threshold
        score = 1 / (1 + np.exp(-5 * (normalized - 1)))
        
        return float(min(score, 1.0))
    
    def _score_ratio(self, value: float, threshold: float) -> float:
        """Score ratio-type factors"""
        if value < threshold:
            return 0.0
        
        # Linear scaling above threshold
        normalized = (value - threshold) / threshold
        score = min(normalized / 2 + 0.5, 1.0)
        
        return float(score)
    
    def _score_imbalance(self, value: float, threshold: float) -> float:
        """Score imbalance factors (-1 to 1 range)"""
        if value < threshold:
            return 0.0
        
        # Scale from threshold to 1.0
        score = (value - threshold) / (1 - threshold)
        
        return float(min(score, 1.0))
    
    def _score_intensity(self, value: float, threshold: float = 3.0) -> float:
        """Score intensity factors"""
        # Assume value is already relative to mean (e.g., 3x mean = value of 3)
        score = min(value / threshold, 1.0)
        return float(score)
    
    def _determine_risk_level(self, confidence: float) -> str:
        """
        Determine risk level based on confidence score
        
        Args:
            confidence: Confidence score (0-1)
            
        Returns:
            Risk level string
        """
        if confidence >= 0.85:
            return 'CRITICAL'
        elif confidence >= 0.75:
            return 'HIGH'
        elif confidence >= 0.65:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _empty_result(self) -> Dict:
        """Return empty detection result"""
        return {
            'is_pump': False,
            'confidence': 0.0,
            'trigger_factors': [],
            'risk_level': 'LOW',
            'factor_scores': {}
        }


if __name__ == "__main__":
    # Test PUMP detector
    import yaml
    
    logger.add("logs/detector.log")
    
    with open("config.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    detector = PumpDetector(config['detection'])
    
    # Simulate strong PUMP signals
    test_factors = {
        'price_velocity_5m': 15.0,      # 15% price increase
        'volume_spike_score': 0.85,     # Strong volume spike
        'buy_sell_ratio': 3.5,          # 3.5x buy pressure
        'bid_ask_imbalance': 0.7,       # Strong buy side
        'trade_intensity': 5.0          # 5x normal intensity
    }
    
    print("\n?? Testing PUMP Detection")
    print("=" * 50)
    
    result = detector.detect(test_factors)
    
    print(f"\nIs PUMP: {result['is_pump']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Risk Level: {result['risk_level']}")
    
    print("\nTriggered Factors:")
    for factor in result['trigger_factors']:
        print(f"  ? {factor['name']}: {factor['value']:.2f} (score: {factor['score']:.2f})")
    
    print("\nFactor Scores:")
    for name, score in result['factor_scores'].items():
        print(f"  ? {name}: {score:.4f}")
