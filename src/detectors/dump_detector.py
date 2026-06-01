"""
DUMP detection logic
"""

import numpy as np
from typing import Dict
from loguru import logger


class DumpDetector:
    """Detects dump events using multi-factor scoring"""
    
    def __init__(self, config: dict):
        """
        Initialize DUMP detector
        
        Args:
            config: Detection configuration from config.yaml
        """
        self.config = config['dump']
        self.enabled = self.config.get('enabled', True)
        
        # Factor weights
        self.weights = self.config['weights']
        
        # Factor thresholds
        self.thresholds = self.config['thresholds']
        
        # Mandatory conditions
        self.mandatory = self.config['mandatory']
        
        # Confidence threshold
        self.confidence_threshold = self.config['confidence_threshold']
        
        logger.info(f"DumpDetector initialized (threshold: {self.confidence_threshold})")
    
    def detect(self, factors: Dict[str, float]) -> Dict:
        """
        Detect DUMP event
        
        Args:
            factors: Dict of calculated factors
            
        Returns:
            Detection result dict
        """
        if not self.enabled:
            return self._empty_result()
        
        try:
            # Check mandatory conditions
            if not self._check_mandatory_conditions(factors):
                return self._empty_result()
            
            # Calculate factor scores
            factor_scores = []
            trigger_factors = []
            
            for factor_name, weight in self.weights.items():
                factor_value = factors.get(factor_name, 0)
                threshold = self.thresholds.get(factor_name, 0)
                
                # Calculate score
                score = self._score_factor(factor_name, factor_value, threshold)
                
                # Weighted score
                weighted_score = score * weight
                factor_scores.append(weighted_score)
                
                # Record triggers
                if score > 0.6:
                    trigger_factors.append({
                        'name': factor_name,
                        'value': float(factor_value),
                        'threshold': float(threshold),
                        'score': float(score),
                        'weight': float(weight)
                    })
            
            # Total score
            total_score = sum(factor_scores)
            
            # Determine if DUMP
            is_dump = total_score >= self.confidence_threshold
            
            # Risk level
            risk_level = self._determine_risk_level(total_score)
            
            result = {
                'is_dump': is_dump,
                'confidence': float(total_score),
                'trigger_factors': trigger_factors,
                'risk_level': risk_level,
                'factor_scores': {name: float(score) for name, score in zip(self.weights.keys(), factor_scores)}
            }
            
            if is_dump:
                logger.warning(f"?? DUMP DETECTED! Confidence: {total_score:.2%}, Risk: {risk_level}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error in DUMP detection: {e}")
            return self._empty_result()
    
    def _check_mandatory_conditions(self, factors: Dict[str, float]) -> bool:
        """Check mandatory conditions"""
        # Must have price drop
        price_velocity = factors.get('price_velocity_5m', 0)
        min_price_drop = self.mandatory.get('min_price_drop', -5.0)
        
        if price_velocity > min_price_drop:  # velocity is negative for drops
            return False
        
        # Must have volume spike
        volume_spike_score = factors.get('volume_spike_score', 0)
        min_volume_spike = self.mandatory.get('min_volume_spike', 0.4)
        
        if volume_spike_score < min_volume_spike:
            return False
        
        return True
    
    def _score_factor(self, factor_name: str, value: float, threshold: float) -> float:
        """Calculate score for individual factor"""
        if factor_name == 'price_velocity_5m':
            return self._score_price_drop(value, threshold)
        
        elif factor_name == 'volume_spike_score':
            return min(value, 1.0)
        
        elif factor_name == 'buy_sell_ratio':
            return self._score_sell_pressure(value, threshold)
        
        elif factor_name == 'bid_ask_imbalance':
            return self._score_sell_imbalance(value, threshold)
        
        elif factor_name == 'price_continuity':
            return self._score_continuity(value, threshold)
        
        else:
            return 0.0
    
    def _score_price_drop(self, value: float, threshold: float) -> float:
        """Score price drop (value and threshold are negative)"""
        if value > 0:
            return 0.0
        
        # Both are negative, so division gives positive
        normalized = value / threshold
        
        # Sigmoid function
        score = 1 / (1 + np.exp(-5 * (normalized - 1)))
        
        return float(min(score, 1.0))
    
    def _score_sell_pressure(self, value: float, threshold: float) -> float:
        """Score sell pressure (low ratio = high sell pressure)"""
        if value > threshold:
            return 0.0
        
        # Inverse scoring: lower value = higher score
        score = (threshold - value) / threshold
        
        return float(min(score, 1.0))
    
    def _score_sell_imbalance(self, value: float, threshold: float) -> float:
        """Score sell-side imbalance (negative values)"""
        if value > threshold:  # threshold is negative
            return 0.0
        
        # Scale from threshold to -1.0
        score = (threshold - value) / abs(threshold)
        
        return float(min(score, 1.0))
    
    def _score_continuity(self, value: float, threshold: float) -> float:
        """Score price continuity (jump ratio)"""
        if value < threshold:
            return 0.0
        
        score = (value - threshold) / (1 - threshold)
        
        return float(min(score, 1.0))
    
    def _determine_risk_level(self, confidence: float) -> str:
        """Determine risk level"""
        if confidence >= 0.85:
            return 'CRITICAL'
        elif confidence >= 0.75:
            return 'HIGH'
        elif confidence >= 0.65:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _empty_result(self) -> Dict:
        """Return empty result"""
        return {
            'is_dump': False,
            'confidence': 0.0,
            'trigger_factors': [],
            'risk_level': 'LOW',
            'factor_scores': {}
        }


if __name__ == "__main__":
    # Test DUMP detector
    import yaml
    
    logger.add("logs/detector.log")
    
    with open("config.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    detector = DumpDetector(config['detection'])
    
    # Simulate strong DUMP signals
    test_factors = {
        'price_velocity_5m': -12.0,     # 12% price drop
        'volume_spike_score': 0.80,     # Strong volume spike
        'buy_sell_ratio': 0.3,          # Heavy sell pressure
        'bid_ask_imbalance': -0.65,     # Strong sell side
        'price_continuity': 0.45        # Many price jumps (panic)
    }
    
    print("\n?? Testing DUMP Detection")
    print("=" * 50)
    
    result = detector.detect(test_factors)
    
    print(f"\nIs DUMP: {result['is_dump']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Risk Level: {result['risk_level']}")
    
    print("\nTriggered Factors:")
    for factor in result['trigger_factors']:
        print(f"  ? {factor['name']}: {factor['value']:.2f} (score: {factor['score']:.2f})")
    
    print("\nFactor Scores:")
    for name, score in result['factor_scores'].items():
        print(f"  ? {name}: {score:.4f}")
