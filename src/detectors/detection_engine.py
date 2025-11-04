"""
Main detection engine
Orchestrates all detectors and event tracking
"""

import yaml
from typing import Dict
from datetime import datetime
from loguru import logger

from .pump_detector import PumpDetector
from .dump_detector import DumpDetector
from .event_tracker import EventTracker


class DetectionEngine:
    """
    Main detection engine
    Coordinates PUMP/DUMP detection and event tracking
    """
    
    def __init__(self, config_path: str = "config.yaml", 
                 postgres_manager=None, redis_manager=None):
        """
        Initialize detection engine
        
        Args:
            config_path: Path to configuration file
            postgres_manager: PostgreSQL manager instance
            redis_manager: Redis manager instance
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.config = config['detection']
        self.pg = postgres_manager
        self.redis = redis_manager
        
        # Initialize detectors
        self.pump_detector = PumpDetector(self.config)
        self.dump_detector = DumpDetector(self.config)
        
        # Initialize event tracker
        self.event_tracker = EventTracker(self.config, postgres_manager)
        
        logger.info("?? DetectionEngine initialized")
    
    def run_detection(self, symbol: str, factors: Dict[str, float], 
                     current_price: float, timestamp: datetime = None) -> Dict:
        """
        Run detection on a single symbol
        
        Args:
            symbol: Trading pair symbol
            factors: Dict of calculated factors
            current_price: Current market price
            timestamp: Timestamp (default: now)
            
        Returns:
            Detection result dict
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        try:
            # Run PUMP detection
            pump_result = self.pump_detector.detect(factors)
            
            # Run DUMP detection
            dump_result = self.dump_detector.detect(factors)
            
            # Determine primary event (higher confidence wins)
            if pump_result['confidence'] >= dump_result['confidence']:
                primary_result = pump_result
                primary_result['event_type'] = 'PUMP'
            else:
                primary_result = dump_result
                primary_result['event_type'] = 'DUMP'
            
            # Update event tracker
            if primary_result['confidence'] >= 0.4:  # Minimum threshold for tracking
                self.event_tracker.update_event(
                    symbol,
                    primary_result,
                    current_price,
                    timestamp
                )
            
            # Cache result in Redis
            if self.redis:
                self._cache_detection_result(symbol, primary_result)
            
            # Add metadata
            primary_result['symbol'] = symbol
            primary_result['timestamp'] = timestamp
            primary_result['price'] = current_price
            
            return primary_result
        
        except Exception as e:
            logger.error(f"Error in detection for {symbol}: {e}")
            return self._empty_result(symbol, current_price, timestamp)
    
    def run_batch_detection(self, symbols_data: Dict) -> Dict[str, Dict]:
        """
        Run detection on multiple symbols
        
        Args:
            symbols_data: Dict of {symbol: {'factors': {...}, 'price': x, 'timestamp': t}}
            
        Returns:
            Dict of {symbol: detection_result}
        """
        results = {}
        
        for symbol, data in symbols_data.items():
            try:
                result = self.run_detection(
                    symbol,
                    data['factors'],
                    data['price'],
                    data.get('timestamp', datetime.now())
                )
                results[symbol] = result
            
            except Exception as e:
                logger.error(f"Error detecting {symbol}: {e}")
                continue
        
        logger.info(f"Completed batch detection for {len(results)} symbols")
        return results
    
    def get_active_events(self) -> Dict:
        """Get all active events"""
        return self.event_tracker.get_active_events()
    
    def get_event_status(self, symbol: str) -> Dict:
        """Get event status for symbol"""
        event = self.event_tracker.get_event(symbol)
        
        if event:
            return {
                'has_active_event': True,
                'event_type': event['event_type'],
                'duration': event['duration'],
                'max_change': event['max_change_percent'],
                'confidence': event['confidence'],
                'risk_level': event['risk_level']
            }
        else:
            return {'has_active_event': False}
    
    def _cache_detection_result(self, symbol: str, result: Dict):
        """Cache detection result in Redis"""
        try:
            cache_data = {
                'event_type': result.get('event_type', 'NONE'),
                'confidence': str(result.get('confidence', 0)),
                'risk_level': result.get('risk_level', 'LOW')
            }
            self.redis.set_detection_status(symbol, cache_data)
        
        except Exception as e:
            logger.error(f"Error caching detection result: {e}")
    
    def _empty_result(self, symbol: str, price: float, timestamp: datetime) -> Dict:
        """Return empty detection result"""
        return {
            'symbol': symbol,
            'event_type': 'NONE',
            'is_pump': False,
            'is_dump': False,
            'confidence': 0.0,
            'trigger_factors': [],
            'risk_level': 'LOW',
            'factor_scores': {},
            'price': price,
            'timestamp': timestamp
        }


if __name__ == "__main__":
    # Test detection engine
    import numpy as np
    from src.storage import init_databases
    
    logger.add("logs/detection.log")
    
    # Initialize databases
    pg, redis = init_databases()
    
    # Create engine
    engine = DetectionEngine(postgres_manager=pg, redis_manager=redis)
    
    print("\n?? Testing Detection Engine")
    print("=" * 50)
    
    # Test 1: PUMP scenario
    pump_factors = {
        'price_velocity_5m': 15.0,
        'volume_spike_score': 0.85,
        'buy_sell_ratio': 3.5,
        'bid_ask_imbalance': 0.7,
        'trade_intensity': 5.0
    }
    
    print("\n1??  Testing PUMP Detection:")
    result = engine.run_detection('PUMPUSDT', pump_factors, 100.0)
    print(f"   Event: {result['event_type']}")
    print(f"   Confidence: {result['confidence']:.2%}")
    print(f"   Risk: {result['risk_level']}")
    
    # Test 2: DUMP scenario
    dump_factors = {
        'price_velocity_5m': -12.0,
        'volume_spike_score': 0.80,
        'buy_sell_ratio': 0.3,
        'bid_ask_imbalance': -0.65,
        'price_continuity': 0.45
    }
    
    print("\n2??  Testing DUMP Detection:")
    result = engine.run_detection('DUMPUSDT', dump_factors, 100.0)
    print(f"   Event: {result['event_type']}")
    print(f"   Confidence: {result['confidence']:.2%}")
    print(f"   Risk: {result['risk_level']}")
    
    # Test 3: Batch detection
    print("\n3??  Testing Batch Detection:")
    batch_data = {
        'COIN1USDT': {
            'factors': pump_factors,
            'price': 50.0,
            'timestamp': datetime.now()
        },
        'COIN2USDT': {
            'factors': dump_factors,
            'price': 75.0,
            'timestamp': datetime.now()
        }
    }
    
    batch_results = engine.run_batch_detection(batch_data)
    for symbol, result in batch_results.items():
        print(f"   {symbol}: {result['event_type']} ({result['confidence']:.2%})")
    
    # Check active events
    print(f"\n?? Active events: {len(engine.get_active_events())}")
    for symbol, event in engine.get_active_events().items():
        print(f"   {symbol}: {event['event_type']} - {event['risk_level']}")
