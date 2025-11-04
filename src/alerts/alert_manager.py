"""
Alert manager
Coordinates all alert channels
"""

import yaml
from typing import Dict, List
from loguru import logger
import asyncio

from .console_alert import ConsoleAlert
from .telegram_alert import TelegramAlert


class AlertManager:
    """Manages all alert channels"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize alert manager
        
        Args:
            config_path: Path to configuration file
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.config = config['alerts']
        self.alert_levels = self.config['levels']
        
        # Initialize alert channels
        self.channels = []
        
        # Console alerts
        if self.config['console']['enabled']:
            self.channels.append(ConsoleAlert(self.config['console']))
        
        # Telegram alerts
        if self.config['telegram']['enabled']:
            self.channels.append(TelegramAlert(self.config['telegram']))
        
        logger.info(f"AlertManager initialized with {len(self.channels)} channels")
    
    def send_detection_alert(self, event: Dict):
        """
        Send alert for new detection
        
        Args:
            event: Event data dict
        """
        try:
            confidence = event.get('confidence', 0)
            risk_level = event.get('risk_level', 'LOW')
            
            # Check if confidence meets alert threshold
            threshold = self.alert_levels.get(risk_level.lower(), 0.5)
            
            if confidence < threshold:
                logger.debug(f"Skipping alert: confidence {confidence:.2%} < threshold {threshold:.2%}")
                return
            
            # Send to all channels
            for channel in self.channels:
                try:
                    if isinstance(channel, ConsoleAlert):
                        channel.send_alert(event)
                    elif isinstance(channel, TelegramAlert):
                        # Run async in event loop
                        asyncio.create_task(channel.send_alert(event))
                except Exception as e:
                    logger.error(f"Error sending alert via {channel.__class__.__name__}: {e}")
        
        except Exception as e:
            logger.error(f"Error in send_detection_alert: {e}")
    
    def send_end_alert(self, event: Dict):
        """
        Send alert for event end
        
        Args:
            event: Event data dict
        """
        try:
            for channel in self.channels:
                try:
                    if isinstance(channel, ConsoleAlert):
                        channel.send_end_alert(event)
                    elif isinstance(channel, TelegramAlert):
                        asyncio.create_task(channel.send_end_alert(event))
                except Exception as e:
                    logger.error(f"Error sending end alert via {channel.__class__.__name__}: {e}")
        
        except Exception as e:
            logger.error(f"Error in send_end_alert: {e}")
    
    def send_custom_alert(self, message: str, level: str = 'INFO'):
        """
        Send custom alert message
        
        Args:
            message: Alert message
            level: Alert level
        """
        # For now, just log it
        if level == 'CRITICAL':
            logger.critical(message)
        elif level == 'WARNING':
            logger.warning(message)
        else:
            logger.info(message)


if __name__ == "__main__":
    # Test alert manager
    from datetime import datetime
    
    logger.add("logs/alerts.log")
    
    manager = AlertManager()
    
    # Test detection alert
    pump_event = {
        'symbol': 'TESTUSDT',
        'event_type': 'PUMP',
        'confidence': 0.85,
        'risk_level': 'CRITICAL',
        'start_price': 100.0,
        'price': 100.0,
        'start_time': datetime.now(),
        'trigger_factors': [
            {'name': 'price_velocity_5m', 'value': 15.0, 'score': 0.9},
            {'name': 'volume_spike_score', 'value': 0.85, 'score': 0.85}
        ]
    }
    
    print("\n?? Testing Alert Manager")
    print("=" * 50)
    
    print("\n1??  Sending detection alert...")
    manager.send_detection_alert(pump_event)
    
    # Test end alert
    end_event = {
        'symbol': 'TESTUSDT',
        'event_type': 'PUMP',
        'duration': 450,
        'max_change_percent': 18.5,
        'start_price': 100.0,
        'peak_price': 118.5,
        'current_price': 110.0
    }
    
    print("\n2??  Sending end alert...")
    manager.send_end_alert(end_event)
    
    print("\n? Alert manager test complete")
