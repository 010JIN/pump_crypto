"""
Telegram alert system
Sends notifications via Telegram bot
"""

import os
from typing import Dict
from datetime import datetime
import asyncio
from loguru import logger

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed. Telegram alerts disabled.")


class TelegramAlert:
    """Send alerts via Telegram bot"""
    
    def __init__(self, config: dict):
        """
        Initialize Telegram alert
        
        Args:
            config: Telegram configuration
        """
        self.enabled = config.get('enabled', False) and TELEGRAM_AVAILABLE
        self.rate_limit = config.get('rate_limit', 5)  # Max alerts per minute
        self.include_charts = config.get('include_charts', False)
        
        if self.enabled:
            token = os.getenv('TELEGRAM_BOT_TOKEN')
            self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
            
            if not token or not self.chat_id:
                logger.warning("Telegram credentials not found. Disabling Telegram alerts.")
                self.enabled = False
            else:
                self.bot = Bot(token=token)
                logger.info("TelegramAlert initialized")
        
        # Rate limiting
        self.alert_count = 0
        self.last_reset_time = datetime.now()
    
    async def send_alert(self, event: Dict):
        """
        Send alert via Telegram
        
        Args:
            event: Event data dict
        """
        if not self.enabled:
            return
        
        # Check rate limit
        if not self._check_rate_limit():
            logger.warning("Telegram rate limit exceeded. Skipping alert.")
            return
        
        try:
            message = self._format_message(event)
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
            self.alert_count += 1
            logger.info(f"Telegram alert sent for {event.get('symbol')}")
        
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
    
    async def send_end_alert(self, event: Dict):
        """
        Send event end notification
        
        Args:
            event: Event data dict
        """
        if not self.enabled:
            return
        
        if not self._check_rate_limit():
            return
        
        try:
            message = self._format_end_message(event)
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
            self.alert_count += 1
            logger.info(f"Telegram end alert sent for {event.get('symbol')}")
        
        except Exception as e:
            logger.error(f"Error sending Telegram end alert: {e}")
    
    def _check_rate_limit(self) -> bool:
        """Check if within rate limit"""
        current_time = datetime.now()
        time_diff = (current_time - self.last_reset_time).total_seconds()
        
        # Reset counter every minute
        if time_diff >= 60:
            self.alert_count = 0
            self.last_reset_time = current_time
        
        return self.alert_count < self.rate_limit
    
    def _format_message(self, event: Dict) -> str:
        """Format alert message for Telegram"""
        symbol = event.get('symbol', 'UNKNOWN')
        event_type = event.get('event_type', 'UNKNOWN')
        confidence = event.get('confidence', 0)
        risk_level = event.get('risk_level', 'LOW')
        price = event.get('start_price', event.get('price', 0))
        timestamp = event.get('start_time', datetime.now())
        
        # Select emoji based on event type and risk
        if event_type == 'PUMP':
            emoji = '??' if risk_level in ['CRITICAL', 'HIGH'] else '??'
        else:
            emoji = '??' if risk_level in ['CRITICAL', 'HIGH'] else '??'
        
        # Risk emoji
        risk_emoji = {
            'CRITICAL': '??',
            'HIGH': '??',
            'MEDIUM': '??',
            'LOW': '??'
        }.get(risk_level, '?')
        
        lines = [
            f"{emoji} *{event_type} DETECTED* {emoji}",
            "",
            f"*Symbol:* `{symbol}`",
            f"*Price:* ${price:.4f}",
            f"*Confidence:* {confidence:.1%}",
            f"*Risk Level:* {risk_emoji} {risk_level}",
            f"*Time:* {timestamp.strftime('%H:%M:%S')}"
        ]
        
        # Add top trigger factors
        trigger_factors = event.get('trigger_factors', [])
        if trigger_factors:
            lines.append("")
            lines.append("*Top Factors:*")
            for factor in trigger_factors[:3]:  # Top 3
                name = factor.get('name', '').replace('_', ' ').title()
                value = factor.get('value', 0)
                lines.append(f"? {name}: {value:.2f}")
        
        return "\n".join(lines)
    
    def _format_end_message(self, event: Dict) -> str:
        """Format end message for Telegram"""
        symbol = event.get('symbol', 'UNKNOWN')
        event_type = event.get('event_type', 'UNKNOWN')
        duration = event.get('duration', 0)
        max_change = event.get('max_change_percent', 0)
        start_price = event.get('start_price', 0)
        end_price = event.get('current_price', 0)
        
        profit_emoji = '?' if max_change > 0 else '?'
        
        lines = [
            f"{profit_emoji} *{event_type} ENDED*",
            "",
            f"*Symbol:* `{symbol}`",
            f"*Duration:* {duration/60:.1f} minutes",
            f"*Max Change:* {max_change:+.2f}%",
            f"*Start Price:* ${start_price:.4f}",
            f"*End Price:* ${end_price:.4f}"
        ]
        
        return "\n".join(lines)


# Sync wrapper for backward compatibility
def send_telegram_alert_sync(config: dict, event: Dict):
    """Synchronous wrapper for sending Telegram alert"""
    alert = TelegramAlert(config)
    asyncio.run(alert.send_alert(event))


if __name__ == "__main__":
    # Test Telegram alert
    from dotenv import load_dotenv
    
    load_dotenv()
    
    config = {
        'enabled': True,
        'rate_limit': 5,
        'include_charts': False
    }
    
    if not TELEGRAM_AVAILABLE:
        print("??  Telegram library not available. Install with: pip install python-telegram-bot")
    else:
        alert = TelegramAlert(config)
        
        if alert.enabled:
            test_event = {
                'symbol': 'BTCUSDT',
                'event_type': 'PUMP',
                'confidence': 0.85,
                'risk_level': 'CRITICAL',
                'start_price': 43250.50,
                'price': 43250.50,
                'start_time': datetime.now(),
                'trigger_factors': [
                    {'name': 'price_velocity_5m', 'value': 15.5},
                    {'name': 'volume_spike_score', 'value': 0.88}
                ]
            }
            
            print("\n?? Sending test Telegram alert...")
            asyncio.run(alert.send_alert(test_event))
            print("? Alert sent!")
        else:
            print("? Telegram alerts not enabled")
