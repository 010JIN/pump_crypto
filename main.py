"""
Crypto Pump & Dump Detection System - Main Entry Point
MVP Phase
"""

import asyncio
import signal
import sys
from datetime import datetime
from loguru import logger
import yaml

from src.storage import init_databases
from src.collectors import BinanceCollector, CoinFilter, DataAggregator
from src.factors import FactorEngine
from src.detectors import DetectionEngine
from src.alerts import AlertManager


class CryptoPumpDumpSystem:
    """Main system orchestrator"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the detection system
        
        Args:
            config_path: Path to configuration file
        """
        logger.info("?? Initializing Crypto Pump & Dump Detection System...")
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize databases
        logger.info("?? Connecting to databases...")
        self.pg, self.redis = init_databases()
        
        # Initialize components
        self.coin_filter = CoinFilter(config_path)
        self.factor_engine = FactorEngine(config_path, self.redis, self.pg)
        self.detection_engine = DetectionEngine(config_path, self.pg, self.redis)
        self.alert_manager = AlertManager(config_path)
        
        # Data collector will be initialized with filtered coins
        self.collector = None
        self.aggregator = None
        
        # System state
        self.is_running = False
        self.monitored_symbols = []
        
        logger.info("? System initialized successfully")
    
    async def start(self):
        """Start the detection system"""
        try:
            self.is_running = True
            
            logger.info("?? Filtering coins for monitoring...")
            
            # Get filtered coins
            from binance.client import Client
            import os
            
            api_key = os.getenv('BINANCE_API_KEY', '')
            api_secret = os.getenv('BINANCE_API_SECRET', '')
            client = Client(api_key, api_secret)
            
            # Filter and prioritize coins
            filtered_coins = self.coin_filter.get_filtered_coins(client)
            self.monitored_symbols = self.coin_filter.filter_by_priority(
                filtered_coins, 
                client, 
                top_n=50  # Monitor top 50
            )
            
            logger.info(f"?? Monitoring {len(self.monitored_symbols)} symbols")
            logger.info(f"   Top 10: {', '.join(self.monitored_symbols[:10])}")
            
            # Initialize data aggregator
            self.aggregator = DataAggregator(self.pg, self.redis)
            
            # Initialize collector with callbacks
            callbacks = {
                'ticker': self.aggregator.on_ticker,
                'kline': self.aggregator.on_kline,
                'trade': self.aggregator.on_trade,
                'depth': self.aggregator.on_depth
            }
            
            self.collector = BinanceCollector(self.monitored_symbols, callbacks)
            
            # Start data collection
            logger.info("?? Starting data collection...")
            await self.collector.start()
            
            # Start detection loop
            logger.info("?? Starting detection loop...")
            await self._detection_loop()
        
        except Exception as e:
            logger.error(f"Error in system startup: {e}")
            raise
    
    async def stop(self):
        """Stop the detection system"""
        logger.info("?? Stopping system...")
        self.is_running = False
        
        if self.collector:
            await self.collector.stop()
        
        logger.info("System stopped")
    
    async def _detection_loop(self):
        """Main detection loop"""
        logger.info("?? Detection loop started")
        
        while self.is_running:
            try:
                # Run detection on all monitored symbols
                await self._run_detection_cycle()
                
                # Sleep interval (e.g., every 5 seconds)
                await asyncio.sleep(5)
            
            except Exception as e:
                logger.error(f"Error in detection loop: {e}")
                await asyncio.sleep(5)
    
    async def _run_detection_cycle(self):
        """Run one detection cycle"""
        try:
            for symbol in self.monitored_symbols:
                # Get cached factors from Redis
                factors = self.redis.get_factors(symbol)
                
                if not factors:
                    # No factors available yet
                    continue
                
                # Get current price
                price_data = self.redis.get_price(symbol)
                if not price_data:
                    continue
                
                current_price = price_data['price']
                timestamp = datetime.now()
                
                # Run detection
                detection_result = self.detection_engine.run_detection(
                    symbol,
                    factors,
                    current_price,
                    timestamp
                )
                
                # Send alerts if detected
                if detection_result.get('is_pump') or detection_result.get('is_dump'):
                    self.alert_manager.send_detection_alert(detection_result)
                
                # Check for ended events
                active_events = self.detection_engine.get_active_events()
                for event_symbol, event in active_events.items():
                    if event['status'] == 'ENDED':
                        self.alert_manager.send_end_alert(event)
        
        except Exception as e:
            logger.error(f"Error in detection cycle: {e}")
    
    async def _factor_calculation_loop(self):
        """
        Background loop for factor calculation
        Calculates factors from collected data
        """
        logger.info("?? Factor calculation loop started")
        
        while self.is_running:
            try:
                for symbol in self.monitored_symbols:
                    # Get recent data from Redis
                    klines = self.redis.get_klines(symbol, '1m', limit=60)
                    
                    if len(klines) < 20:
                        # Not enough data yet
                        continue
                    
                    # Prepare data snapshot
                    prices = [k['close'] for k in klines]
                    volumes = [k['volume'] for k in klines]
                    
                    data_snapshot = {
                        'prices': prices,
                        'volumes': volumes,
                        'current_volume': volumes[-1] if volumes else 0,
                        'taker_buy_volume': klines[-1].get('taker_buy_volume', 0) if klines else 0,
                        'orderbook': self.redis.get_orderbook(symbol) or {'bids': [], 'asks': []},
                        'current_price': prices[-1] if prices else 0,
                        'trade_count': klines[-1].get('trades', 0) if klines else 0
                    }
                    
                    # Calculate factors
                    factors = self.factor_engine.calculate_all_factors(symbol, data_snapshot)
                    
                    # Save factors
                    if factors:
                        self.factor_engine.save_factors(symbol, factors)
                
                # Sleep for 1 minute
                await asyncio.sleep(60)
            
            except Exception as e:
                logger.error(f"Error in factor calculation loop: {e}")
                await asyncio.sleep(60)


async def main():
    """Main entry point"""
    # Configure logging
    logger.remove()
    logger.add(
        "logs/crypto_monitor_{time:YYYY-MM-DD}.log",
        rotation="100 MB",
        retention="30 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
    )
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    
    logger.info("=" * 70)
    logger.info("?? Crypto Pump & Dump Detection System - MVP")
    logger.info("=" * 70)
    
    # Initialize system
    system = CryptoPumpDumpSystem()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(system.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start system
    try:
        await system.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await system.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        await system.stop()
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n?? Shutting down gracefully...")
    except Exception as e:
        logger.error(f"System crashed: {e}")
        sys.exit(1)
