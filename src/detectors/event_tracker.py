"""
Event lifecycle tracker
Tracks pump & dump events from start to finish
"""

from typing import Dict, Optional
from datetime import datetime
from loguru import logger


class EventTracker:
    """Tracks lifecycle of detection events"""
    
    def __init__(self, config: dict, postgres_manager=None):
        """
        Initialize event tracker
        
        Args:
            config: Event tracking configuration
            postgres_manager: PostgreSQL manager instance
        """
        self.config = config['event_tracking']
        self.pg = postgres_manager
        
        # Active events: {symbol: event_data}
        self.active_events = {}
        
        # Configuration
        self.max_duration = self.config.get('max_event_duration', 1800)  # 30 min
        self.retracement_threshold = self.config.get('retracement_threshold', 0.5)
        self.low_confidence_timeout = self.config.get('low_confidence_timeout', 180)  # 3 min
        
        # Tracking state
        self.low_confidence_counters = {}  # {symbol: consecutive_seconds}
        
        logger.info(f"EventTracker initialized (max duration: {self.max_duration}s)")
    
    def update_event(self, symbol: str, detection_result: Dict, 
                    current_price: float, timestamp: datetime):
        """
        Update or create event
        
        Args:
            symbol: Trading pair symbol
            detection_result: Detection result from detector
            current_price: Current market price
            timestamp: Current timestamp
        """
        event_type = self._determine_event_type(detection_result)
        confidence = detection_result.get('confidence', 0)
        
        # If no significant event detected
        if confidence < 0.4:
            # Track low confidence time
            if symbol in self.active_events:
                self._track_low_confidence(symbol)
            return
        
        # Reset low confidence counter
        if symbol in self.low_confidence_counters:
            self.low_confidence_counters[symbol] = 0
        
        # Create new event or update existing
        if symbol not in self.active_events:
            if confidence >= 0.65:
                self._create_event(symbol, event_type, detection_result, 
                                 current_price, timestamp)
        else:
            self._update_existing_event(symbol, detection_result, 
                                       current_price, timestamp)
    
    def _determine_event_type(self, detection_result: Dict) -> str:
        """Determine event type from detection result"""
        if detection_result.get('is_pump', False):
            return 'PUMP'
        elif detection_result.get('is_dump', False):
            return 'DUMP'
        return 'UNKNOWN'
    
    def _create_event(self, symbol: str, event_type: str, detection_result: Dict,
                     current_price: float, timestamp: datetime):
        """Create new event"""
        event = {
            'symbol': symbol,
            'event_type': event_type,
            'start_time': timestamp,
            'start_price': current_price,
            'peak_price': current_price,
            'current_price': current_price,
            'max_change_percent': 0.0,
            'confidence': detection_result['confidence'],
            'trigger_factors': detection_result['trigger_factors'],
            'risk_level': detection_result['risk_level'],
            'status': 'ACTIVE',
            'duration': 0
        }
        
        self.active_events[symbol] = event
        
        # Save to database
        self._save_event(event)
        
        # Log alert
        logger.warning(
            f"?? NEW {event_type} EVENT: {symbol} | "
            f"Price: ${current_price:.4f} | "
            f"Confidence: {event['confidence']:.2%} | "
            f"Risk: {event['risk_level']}"
        )
    
    def _update_existing_event(self, symbol: str, detection_result: Dict,
                               current_price: float, timestamp: datetime):
        """Update existing event"""
        event = self.active_events[symbol]
        event_type = event['event_type']
        
        # Update current state
        event['current_price'] = current_price
        event['duration'] = (timestamp - event['start_time']).total_seconds()
        event['confidence'] = detection_result['confidence']
        
        # Update peak/trough
        if event_type == 'PUMP':
            if current_price > event['peak_price']:
                event['peak_price'] = current_price
            
            event['max_change_percent'] = (
                (event['peak_price'] - event['start_price']) / 
                event['start_price'] * 100
            )
        
        elif event_type == 'DUMP':
            if current_price < event['peak_price']:
                event['peak_price'] = current_price  # Peak is actually lowest
            
            event['max_change_percent'] = (
                (event['start_price'] - event['peak_price']) / 
                event['start_price'] * 100
            )
        
        # Check if event should end
        if self._should_end_event(event, detection_result):
            self._end_event(symbol)
        else:
            # Update database
            self._update_event_db(event)
    
    def _track_low_confidence(self, symbol: str):
        """Track consecutive low confidence periods"""
        if symbol not in self.low_confidence_counters:
            self.low_confidence_counters[symbol] = 0
        
        self.low_confidence_counters[symbol] += 1
        
        # End event if low confidence for too long
        if self.low_confidence_counters[symbol] >= self.low_confidence_timeout:
            logger.info(f"Ending {symbol} event due to low confidence timeout")
            self._end_event(symbol)
    
    def _should_end_event(self, event: Dict, detection_result: Dict) -> bool:
        """
        Determine if event should end
        
        Conditions:
        1. Price retracement exceeds threshold
        2. Duration exceeds maximum
        3. Confidence drops significantly
        """
        # Condition 1: Retracement
        if event['event_type'] == 'PUMP':
            if event['peak_price'] > event['start_price']:
                retracement = (
                    (event['peak_price'] - event['current_price']) / 
                    (event['peak_price'] - event['start_price'])
                )
                if retracement > self.retracement_threshold:
                    logger.info(f"{event['symbol']}: Retracement {retracement:.1%} > threshold")
                    return True
        
        elif event['event_type'] == 'DUMP':
            if event['start_price'] > event['peak_price']:
                recovery = (
                    (event['current_price'] - event['peak_price']) / 
                    (event['start_price'] - event['peak_price'])
                )
                if recovery > self.retracement_threshold:
                    logger.info(f"{event['symbol']}: Recovery {recovery:.1%} > threshold")
                    return True
        
        # Condition 2: Max duration
        if event['duration'] > self.max_duration:
            logger.info(f"{event['symbol']}: Duration {event['duration']:.0f}s exceeds maximum")
            return True
        
        # Condition 3: Low confidence (handled by _track_low_confidence)
        
        return False
    
    def _end_event(self, symbol: str):
        """End an active event"""
        if symbol not in self.active_events:
            return
        
        event = self.active_events[symbol]
        event['status'] = 'ENDED'
        
        # Update database
        self._update_event_db(event)
        
        # Log
        logger.info(
            f"? {event['event_type']} EVENT ENDED: {symbol} | "
            f"Duration: {event['duration']:.0f}s | "
            f"Max change: {event['max_change_percent']:.2f}% | "
            f"Start: ${event['start_price']:.4f} ? Peak: ${event['peak_price']:.4f}"
        )
        
        # Remove from active events
        del self.active_events[symbol]
        
        # Clean up counters
        if symbol in self.low_confidence_counters:
            del self.low_confidence_counters[symbol]
    
    def _save_event(self, event: Dict):
        """Save new event to database"""
        if not self.pg:
            return
        
        try:
            from src.storage import DetectionEvent
            import json
            
            with self.pg.session_scope() as session:
                db_event = DetectionEvent(
                    symbol=event['symbol'],
                    event_type=event['event_type'],
                    confidence_score=event['confidence'],
                    trigger_factors=json.dumps(event['trigger_factors']),
                    start_time=event['start_time'],
                    detection_time=event['start_time'],
                    start_price=event['start_price'],
                    current_price=event['current_price'],
                    peak_price=event['peak_price'],
                    max_change_percent=event['max_change_percent'],
                    status=event['status']
                )
                session.add(db_event)
        
        except Exception as e:
            logger.error(f"Error saving event to database: {e}")
    
    def _update_event_db(self, event: Dict):
        """Update event in database"""
        if not self.pg:
            return
        
        try:
            from src.storage import DetectionEvent
            
            with self.pg.session_scope() as session:
                # Find and update the event
                db_event = session.query(DetectionEvent).filter(
                    DetectionEvent.symbol == event['symbol'],
                    DetectionEvent.status == 'ACTIVE'
                ).first()
                
                if db_event:
                    db_event.current_price = event['current_price']
                    db_event.peak_price = event['peak_price']
                    db_event.max_change_percent = event['max_change_percent']
                    db_event.confidence_score = event['confidence']
                    db_event.status = event['status']
        
        except Exception as e:
            logger.error(f"Error updating event in database: {e}")
    
    def get_active_events(self) -> Dict:
        """Get all active events"""
        return self.active_events.copy()
    
    def get_event(self, symbol: str) -> Optional[Dict]:
        """Get event for specific symbol"""
        return self.active_events.get(symbol)


if __name__ == "__main__":
    # Test event tracker
    import yaml
    from src.storage import init_databases
    
    logger.add("logs/tracker.log")
    
    with open("config.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    pg, _ = init_databases()
    
    tracker = EventTracker(config['detection'], postgres_manager=pg)
    
    # Simulate PUMP event
    detection_result = {
        'is_pump': True,
        'confidence': 0.85,
        'trigger_factors': [
            {'name': 'price_velocity_5m', 'value': 15.0, 'score': 0.9},
            {'name': 'volume_spike_score', 'value': 0.85, 'score': 0.85}
        ],
        'risk_level': 'CRITICAL'
    }
    
    print("\n?? Testing Event Tracker")
    print("=" * 50)
    
    # Create event
    tracker.update_event('TESTUSDT', detection_result, 100.0, datetime.now())
    
    print(f"\nActive events: {len(tracker.get_active_events())}")
    
    event = tracker.get_event('TESTUSDT')
    if event:
        print(f"\nEvent details:")
        print(f"  Type: {event['event_type']}")
        print(f"  Confidence: {event['confidence']:.2%}")
        print(f"  Risk: {event['risk_level']}")
        print(f"  Status: {event['status']}")
