"""
Factor calculation engine
Orchestrates all factor calculations
"""

import yaml
from typing import Dict, Optional
from datetime import datetime
from loguru import logger

from .price_factors import PriceFactors
from .volume_factors import VolumeFactors
from .liquidity_factors import LiquidityFactors
from .market_factors import MarketFactors


class FactorEngine:
    """
    Main engine for calculating all factors
    Coordinates data collection and factor computation
    """
    
    def __init__(self, config_path: str = "config.yaml", redis_manager=None, postgres_manager=None):
        """
        Initialize factor engine
        
        Args:
            config_path: Path to configuration file
            redis_manager: Redis manager instance
            postgres_manager: PostgreSQL manager instance
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.config = config['factors']
        self.redis = redis_manager
        self.pg = postgres_manager
        
        logger.info("FactorEngine initialized")
    
    def calculate_all_factors(self, symbol: str, data_snapshot: Dict) -> Dict[str, float]:
        """
        Calculate all factors for a symbol
        
        Args:
            symbol: Trading pair symbol
            data_snapshot: Dict containing all necessary data:
                - prices: List of recent prices
                - volumes: List of recent volumes
                - current_volume: Current period volume
                - taker_buy_volume: Taker buy volume
                - trade_volumes: Individual trade volumes
                - orderbook: Order book data (bids, asks)
                - current_price: Current market price
                - trade_count: Number of trades
                - previous_depth: Previous order book depth
                
        Returns:
            Dict of all calculated factors
        """
        all_factors = {}
        
        try:
            # 1. Price factors
            if 'prices' in data_snapshot and len(data_snapshot['prices']) > 0:
                price_factors = PriceFactors.calculate_all(
                    data_snapshot['prices'],
                    self.config['price']
                )
                all_factors.update(price_factors)
                logger.debug(f"{symbol}: Calculated {len(price_factors)} price factors")
            
            # 2. Volume factors
            volume_data = {
                'current_volume': data_snapshot.get('current_volume', 0),
                'historical_volumes': data_snapshot.get('volumes', []),
                'taker_buy_volume': data_snapshot.get('taker_buy_volume', 0),
                'trade_volumes': data_snapshot.get('trade_volumes', [])
            }
            
            volume_factors = VolumeFactors.calculate_all(
                volume_data,
                self.config['volume']
            )
            all_factors.update(volume_factors)
            logger.debug(f"{symbol}: Calculated {len(volume_factors)} volume factors")
            
            # 3. Liquidity factors
            if 'orderbook' in data_snapshot and 'current_price' in data_snapshot:
                liquidity_factors = LiquidityFactors.calculate_all(
                    data_snapshot['orderbook'],
                    data_snapshot['current_price'],
                    self.config['liquidity']
                )
                all_factors.update(liquidity_factors)
                logger.debug(f"{symbol}: Calculated {len(liquidity_factors)} liquidity factors")
            
            # 4. Market factors
            market_data = {
                'trade_count': data_snapshot.get('trade_count', 0),
                'window_minutes': 1,
                'prices': data_snapshot.get('prices', []),
                'volumes': data_snapshot.get('volumes', []),
                'current_depth': data_snapshot.get('current_depth', 0),
                'previous_depth': data_snapshot.get('previous_depth', 0),
                'price_changes': data_snapshot.get('price_changes', []),
                'volume_changes': data_snapshot.get('volume_changes', [])
            }
            
            market_factors = MarketFactors.calculate_all(
                market_data,
                self.config.get('market', {})
            )
            all_factors.update(market_factors)
            logger.debug(f"{symbol}: Calculated {len(market_factors)} market factors")
            
            # Add metadata
            all_factors['symbol'] = symbol
            all_factors['timestamp'] = datetime.now().timestamp()
            all_factors['factor_count'] = len(all_factors) - 2  # Exclude symbol and timestamp
            
            logger.info(f"? {symbol}: Calculated {all_factors['factor_count']} total factors")
            
            return all_factors
        
        except Exception as e:
            logger.error(f"Error calculating factors for {symbol}: {e}")
            return {}
    
    def save_factors(self, symbol: str, factors: Dict[str, float]):
        """
        Save calculated factors to storage
        
        Args:
            symbol: Trading pair symbol
            factors: Dict of calculated factors
        """
        try:
            # Save to Redis cache
            if self.redis:
                self.redis.set_factors(symbol, {k: str(v) for k, v in factors.items()})
            
            # Save to PostgreSQL
            if self.pg:
                from src.storage import FactorValue
                
                with self.pg.session_scope() as session:
                    factor_record = FactorValue(
                        symbol=symbol,
                        timestamp=datetime.fromtimestamp(factors['timestamp']),
                        price_velocity_1m=factors.get('price_velocity_1m'),
                        price_velocity_5m=factors.get('price_velocity_5m'),
                        price_velocity_15m=factors.get('price_velocity_15m'),
                        price_acceleration=factors.get('price_acceleration'),
                        price_volatility=factors.get('price_volatility'),
                        volume_ratio_1m=factors.get('volume_ratio'),
                        volume_spike_score=factors.get('volume_spike_score'),
                        buy_sell_ratio=factors.get('buy_sell_ratio'),
                        large_trade_ratio=factors.get('large_trade_ratio'),
                        liquidity_score=factors.get('liquidity_score'),
                        bid_ask_imbalance=factors.get('bid_ask_imbalance'),
                        spread_percent=factors.get('spread_percent'),
                        orderbook_pressure=factors.get('orderbook_pressure'),
                        trade_intensity=factors.get('trade_intensity'),
                        price_continuity=factors.get('price_continuity'),
                        rsi=factors.get('rsi')
                    )
                    session.merge(factor_record)
            
            logger.debug(f"Saved factors for {symbol}")
        
        except Exception as e:
            logger.error(f"Error saving factors for {symbol}: {e}")
    
    def get_cached_factors(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Get cached factors from Redis
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dict of factors or None
        """
        if not self.redis:
            return None
        
        return self.redis.get_factors(symbol)


if __name__ == "__main__":
    # Test factor engine
    import numpy as np
    from src.storage import init_databases
    
    logger.add("logs/factors.log")
    
    # Initialize databases
    pg, redis = init_databases()
    
    # Create engine
    engine = FactorEngine(redis_manager=redis, postgres_manager=pg)
    
    # Simulate data snapshot
    prices = [100 + i * 0.3 + np.random.normal(0, 0.5) for i in range(60)]
    volumes = [1000 + np.random.normal(0, 100) for _ in range(60)]
    
    data_snapshot = {
        'prices': prices,
        'volumes': volumes,
        'current_volume': 1500,  # Volume spike
        'taker_buy_volume': 1000,  # 67% buy pressure
        'trade_volumes': [10, 15, 8, 50, 12, 200, 9],
        'orderbook': {
            'bids': [[99.5, 10], [99.0, 15], [98.5, 8]],
            'asks': [[100.5, 5], [101.0, 7], [101.5, 4]]
        },
        'current_price': 100.0,
        'trade_count': 150,
        'current_depth': 5000,
        'previous_depth': 4500,
        'price_changes': [1.5, -0.5, 2.0],
        'volume_changes': [20, -10, 50]
    }
    
    # Calculate factors
    print("\n?? Calculating all factors...")
    factors = engine.calculate_all_factors('TESTUSDT', data_snapshot)
    
    print("\n?? All Calculated Factors:")
    for key, value in factors.items():
        if key not in ['symbol', 'timestamp', 'factor_count']:
            print(f"  {key}: {value:.4f}")
    
    print(f"\nTotal: {factors['factor_count']} factors")
    
    # Save factors
    print("\n?? Saving factors...")
    engine.save_factors('TESTUSDT', factors)
    
    # Retrieve from cache
    print("\n?? Retrieving from cache...")
    cached = engine.get_cached_factors('TESTUSDT')
    print(f"Cached factors: {len(cached) if cached else 0}")
