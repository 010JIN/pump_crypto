"""
Console-based alert system
Displays alerts in terminal with colors
"""

from typing import Dict
from datetime import datetime
from loguru import logger


class ConsoleAlert:
    """Display alerts in console with colors"""
    
    def __init__(self, config: dict):
        """
        Initialize console alert
        
        Args:
            config: Console alert configuration
        """
        self.enabled = config.get('enabled', True)
        self.use_colors = config.get('color_output', True)
        
        # ANSI color codes
        self.colors = {
            'CRITICAL': '\033[91m',  # Red
            'HIGH': '\033[93m',      # Yellow
            'MEDIUM': '\033[94m',    # Blue
            'LOW': '\033[92m',       # Green
            'RESET': '\033[0m',      # Reset
            'BOLD': '\033[1m',       # Bold
            'PUMP': '\033[92m',      # Green
            'DUMP': '\033[91m'       # Red
        }
        
        logger.info("ConsoleAlert initialized")
    
    def send_alert(self, event: Dict):
        """
        Send alert to console
        
        Args:
            event: Event data dict
        """
        if not self.enabled:
            return
        
        try:
            # Build alert message
            message = self._format_alert(event)
            
            # Print with colors if enabled
            if self.use_colors:
                print(message)
            else:
                # Strip color codes
                plain_message = self._strip_colors(message)
                print(plain_message)
        
        except Exception as e:
            logger.error(f"Error sending console alert: {e}")
    
    def send_end_alert(self, event: Dict):
        """
        Send event end notification
        
        Args:
            event: Event data dict
        """
        if not self.enabled:
            return
        
        try:
            message = self._format_end_alert(event)
            
            if self.use_colors:
                print(message)
            else:
                print(self._strip_colors(message))
        
        except Exception as e:
            logger.error(f"Error sending end alert: {e}")
    
    def _format_alert(self, event: Dict) -> str:
        """Format alert message with colors"""
        symbol = event.get('symbol', 'UNKNOWN')
        event_type = event.get('event_type', 'UNKNOWN')
        confidence = event.get('confidence', 0)
        risk_level = event.get('risk_level', 'LOW')
        price = event.get('start_price', event.get('price', 0))
        timestamp = event.get('start_time', datetime.now())
        
        # Get colors
        risk_color = self.colors.get(risk_level, '')
        event_color = self.colors.get(event_type, '')
        bold = self.colors.get('BOLD', '')
        reset = self.colors.get('RESET', '')
        
        # Build message
        lines = [
            "\n" + "=" * 70,
            f"{bold}{event_color}?? {event_type} DETECTED!{reset}",
            "=" * 70,
            f"{bold}Symbol:{reset}      {symbol}",
            f"{bold}Price:{reset}       ${price:.4f}",
            f"{bold}Confidence:{reset}  {risk_color}{confidence:.2%}{reset}",
            f"{bold}Risk Level:{reset}  {risk_color}{risk_level}{reset}",
            f"{bold}Time:{reset}        {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        
        # Add trigger factors
        trigger_factors = event.get('trigger_factors', [])
        if trigger_factors:
            lines.append(f"\n{bold}Trigger Factors:{reset}")
            for factor in trigger_factors:
                name = factor.get('name', '')
                value = factor.get('value', 0)
                score = factor.get('score', 0)
                lines.append(f"  ? {name}: {value:.2f} (score: {score:.2f})")
        
        lines.append("=" * 70 + "\n")
        
        return "\n".join(lines)
    
    def _format_end_alert(self, event: Dict) -> str:
        """Format event end message"""
        symbol = event.get('symbol', 'UNKNOWN')
        event_type = event.get('event_type', 'UNKNOWN')
        duration = event.get('duration', 0)
        max_change = event.get('max_change_percent', 0)
        start_price = event.get('start_price', 0)
        peak_price = event.get('peak_price', 0)
        end_price = event.get('current_price', 0)
        
        bold = self.colors.get('BOLD', '')
        reset = self.colors.get('RESET', '')
        
        lines = [
            "\n" + "-" * 70,
            f"{bold}? {event_type} EVENT ENDED{reset}",
            "-" * 70,
            f"{bold}Symbol:{reset}       {symbol}",
            f"{bold}Duration:{reset}     {duration:.0f} seconds ({duration/60:.1f} minutes)",
            f"{bold}Max Change:{reset}   {max_change:.2f}%",
            f"{bold}Start Price:{reset}  ${start_price:.4f}",
            f"{bold}Peak Price:{reset}   ${peak_price:.4f}",
            f"{bold}End Price:{reset}    ${end_price:.4f}",
            "-" * 70 + "\n"
        ]
        
        return "\n".join(lines)
    
    def _strip_colors(self, text: str) -> str:
        """Remove ANSI color codes"""
        import re
        ansi_escape = re.compile(r'\033\[[0-9;]*m')
        return ansi_escape.sub('', text)


if __name__ == "__main__":
    # Test console alert
    config = {
        'enabled': True,
        'color_output': True
    }
    
    alert = ConsoleAlert(config)
    
    # Test pump alert
    pump_event = {
        'symbol': 'BTCUSDT',
        'event_type': 'PUMP',
        'confidence': 0.85,
        'risk_level': 'CRITICAL',
        'start_price': 43250.50,
        'price': 43250.50,
        'start_time': datetime.now(),
        'trigger_factors': [
            {'name': 'price_velocity_5m', 'value': 15.5, 'score': 0.92},
            {'name': 'volume_spike_score', 'value': 0.88, 'score': 0.88},
            {'name': 'buy_sell_ratio', 'value': 3.8, 'score': 0.85}
        ]
    }
    
    print("\n?? Testing Console Alert - PUMP")
    alert.send_alert(pump_event)
    
    # Test end alert
    end_event = {
        'symbol': 'BTCUSDT',
        'event_type': 'PUMP',
        'duration': 450,
        'max_change_percent': 18.5,
        'start_price': 43250.50,
        'peak_price': 51250.00,
        'current_price': 47800.00
    }
    
    print("\n?? Testing End Alert")
    alert.send_end_alert(end_event)
