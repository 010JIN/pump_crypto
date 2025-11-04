"""
Market microstructure factor calculations
"""

import numpy as np
from typing import List, Dict
from loguru import logger


class MarketFactors:
    """Calculate market microstructure factors"""
    
    @staticmethod
    def calculate_trade_intensity(trade_count: int, window_minutes: int = 1) -> float:
        """
        Calculate trading intensity (trades per minute)
        
        Args:
            trade_count: Number of trades in window
            window_minutes: Time window in minutes
            
        Returns:
            Trades per minute
        """
        if window_minutes == 0:
            return 0.0
        
        intensity = trade_count / window_minutes
        return float(intensity)
    
    @staticmethod
    def calculate_price_continuity(prices: List[float], threshold: float = 0.005) -> float:
        """
        Calculate price continuity (ratio of price jumps)
        
        Args:
            prices: List of prices
            threshold: Jump threshold (default 0.5%)
            
        Returns:
            Jump ratio (0-1)
        """
        if len(prices) < 2:
            return 0.0
        
        price_changes = np.diff(prices)
        price_returns = price_changes / np.array(prices[:-1])
        
        jumps = np.abs(price_returns) > threshold
        jump_ratio = np.sum(jumps) / len(price_returns)
        
        return float(jump_ratio)
    
    @staticmethod
    def calculate_depth_change_rate(current_depth: float, previous_depth: float) -> float:
        """
        Calculate rate of change in order book depth
        
        Args:
            current_depth: Current total depth
            previous_depth: Previous total depth
            
        Returns:
            Change rate as percentage
        """
        if previous_depth == 0:
            return 0.0
        
        change_rate = (current_depth - previous_depth) / previous_depth * 100
        return float(change_rate)
    
    @staticmethod
    def calculate_market_efficiency(prices: List[float], volumes: List[float]) -> float:
        """
        Calculate market efficiency ratio
        (How efficiently price moves relative to volume)
        
        Args:
            prices: List of prices
            volumes: List of volumes
            
        Returns:
            Efficiency ratio
        """
        if len(prices) < 2 or len(volumes) < 1:
            return 0.0
        
        # Price movement
        price_range = max(prices) - min(prices)
        avg_price = np.mean(prices)
        
        if avg_price == 0:
            return 0.0
        
        price_movement = price_range / avg_price
        
        # Volume
        total_volume = sum(volumes)
        
        if total_volume == 0:
            return 0.0
        
        # Efficiency: price movement per unit volume
        efficiency = price_movement / total_volume * 1000000  # Scale up
        
        return float(efficiency)
    
    @staticmethod
    def calculate_momentum_score(price_changes: List[float], volume_changes: List[float]) -> float:
        """
        Calculate momentum score combining price and volume changes
        
        Args:
            price_changes: List of price change percentages
            volume_changes: List of volume change percentages
            
        Returns:
            Momentum score
        """
        if not price_changes or not volume_changes:
            return 0.0
        
        # Average positive momentum
        positive_price_momentum = np.mean([p for p in price_changes if p > 0]) if any(p > 0 for p in price_changes) else 0
        positive_volume_momentum = np.mean([v for v in volume_changes if v > 0]) if any(v > 0 for v in volume_changes) else 0
        
        # Combined score (geometric mean)
        if positive_price_momentum > 0 and positive_volume_momentum > 0:
            momentum_score = np.sqrt(positive_price_momentum * positive_volume_momentum)
        else:
            momentum_score = 0
        
        return float(momentum_score)
    
    @staticmethod
    def calculate_all(market_data: Dict, config: dict) -> Dict[str, float]:
        """
        Calculate all market factors
        
        Args:
            market_data: Dict containing market microstructure data
            config: Configuration dict
            
        Returns:
            Dict of all calculated factors
        """
        try:
            factors = {}
            
            # Trade intensity
            if 'trade_count' in market_data:
                window = market_data.get('window_minutes', 1)
                factors['trade_intensity'] = MarketFactors.calculate_trade_intensity(
                    market_data['trade_count'],
                    window
                )
            
            # Price continuity
            if 'prices' in market_data:
                factors['price_continuity'] = MarketFactors.calculate_price_continuity(
                    market_data['prices']
                )
            
            # Depth change rate
            if 'current_depth' in market_data and 'previous_depth' in market_data:
                factors['depth_change_rate'] = MarketFactors.calculate_depth_change_rate(
                    market_data['current_depth'],
                    market_data['previous_depth']
                )
            
            # Market efficiency
            if 'prices' in market_data and 'volumes' in market_data:
                factors['market_efficiency'] = MarketFactors.calculate_market_efficiency(
                    market_data['prices'],
                    market_data['volumes']
                )
            
            # Momentum score
            if 'price_changes' in market_data and 'volume_changes' in market_data:
                factors['momentum_score'] = MarketFactors.calculate_momentum_score(
                    market_data['price_changes'],
                    market_data['volume_changes']
                )
            
            return factors
        
        except Exception as e:
            logger.error(f"Error calculating market factors: {e}")
            return {}


if __name__ == "__main__":
    # Test market factors
    logger.add("logs/factors.log")
    
    # Simulate market data
    prices = [100 + i * 0.5 + np.random.normal(0, 0.2) for i in range(20)]
    volumes = [1000 + np.random.normal(0, 100) for _ in range(20)]
    
    market_data = {
        'trade_count': 150,
        'window_minutes': 1,
        'prices': prices,
        'volumes': volumes,
        'current_depth': 5000,
        'previous_depth': 4500,
        'price_changes': [1.5, -0.5, 2.0, 0.8, -0.3],
        'volume_changes': [20, -10, 50, 15, -5]
    }
    
    config = {}
    
    factors = MarketFactors.calculate_all(market_data, config)
    
    print("\n?? Market Factors:")
    for key, value in factors.items():
        print(f"  {key}: {value:.4f}")
