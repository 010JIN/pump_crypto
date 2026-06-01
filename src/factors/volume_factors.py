"""
Volume-based factor calculations
"""

import numpy as np
from typing import List, Dict
from loguru import logger


class VolumeFactors:
    """Calculate volume-related factors"""
    
    @staticmethod
    def calculate_volume_ratio(current_volume: float, historical_volumes: List[float], 
                               window: int = 60) -> float:
        """
        Calculate volume ratio (current / average)
        
        Args:
            current_volume: Current period volume
            historical_volumes: List of historical volumes
            window: Window for average calculation
            
        Returns:
            Volume ratio
        """
        if len(historical_volumes) < window:
            return 1.0
        
        recent_volumes = historical_volumes[-window:]
        avg_volume = np.mean(recent_volumes)
        
        if avg_volume == 0:
            return 1.0
        
        ratio = current_volume / avg_volume
        return float(ratio)
    
    @staticmethod
    def calculate_volume_spike_score(volumes: List[float], window: int = 60) -> float:
        """
        Calculate volume spike score using z-score
        
        Args:
            volumes: List of volume values
            window: Window for statistics
            
        Returns:
            Score between 0-1 (1 = extreme spike)
        """
        if len(volumes) < window + 1:
            return 0.0
        
        current_volume = volumes[-1]
        historical_volumes = volumes[-window-1:-1]
        
        mean_volume = np.mean(historical_volumes)
        std_volume = np.std(historical_volumes)
        
        if std_volume == 0:
            return 0.0
        
        # Calculate z-score
        z_score = (current_volume - mean_volume) / std_volume
        
        # Convert to 0-1 score using sigmoid
        # Shift by 3 so that z=3 (3 std devs) maps to ~0.5
        score = 1 / (1 + np.exp(-z_score + 3))
        
        return float(min(score, 1.0))
    
    @staticmethod
    def calculate_volume_trend(volumes: List[float], short_window: int = 5, 
                               long_window: int = 15) -> float:
        """
        Calculate volume trend (short MA / long MA - 1)
        
        Args:
            volumes: List of volumes
            short_window: Short moving average window
            long_window: Long moving average window
            
        Returns:
            Trend value as percentage
        """
        if len(volumes) < long_window:
            return 0.0
        
        ma_short = np.mean(volumes[-short_window:])
        ma_long = np.mean(volumes[-long_window:])
        
        if ma_long == 0:
            return 0.0
        
        trend = (ma_short - ma_long) / ma_long * 100
        return float(trend)
    
    @staticmethod
    def calculate_buy_sell_ratio(taker_buy_volume: float, total_volume: float) -> float:
        """
        Calculate buy/sell pressure ratio
        
        Args:
            taker_buy_volume: Volume from taker buy orders
            total_volume: Total volume
            
        Returns:
            Buy/sell ratio
        """
        if total_volume == 0:
            return 1.0
        
        taker_sell_volume = total_volume - taker_buy_volume
        
        if taker_sell_volume == 0:
            return 999.0  # Extreme buy pressure
        
        ratio = taker_buy_volume / taker_sell_volume
        return float(ratio)
    
    @staticmethod
    def calculate_large_trade_ratio(trade_volumes: List[float]) -> float:
        """
        Calculate ratio of large trades
        
        Args:
            trade_volumes: List of individual trade volumes
            
        Returns:
            Ratio of large trades (0-1)
        """
        if not trade_volumes:
            return 0.0
        
        avg_volume = np.mean(trade_volumes)
        threshold = avg_volume * 3  # Define large as 3x average
        
        large_trades = len([v for v in trade_volumes if v > threshold])
        ratio = large_trades / len(trade_volumes)
        
        return float(ratio)
    
    @staticmethod
    def calculate_all(volume_data: Dict, config: dict) -> Dict[str, float]:
        """
        Calculate all volume factors
        
        Args:
            volume_data: Dict containing:
                - current_volume: Current period volume
                - historical_volumes: List of historical volumes
                - taker_buy_volume: Taker buy volume
                - trade_volumes: List of individual trade volumes
            config: Configuration dict
            
        Returns:
            Dict of all calculated factors
        """
        try:
            factors = {}
            
            # Volume ratio
            ratio_window = config.get('ratio_window', 60)
            if 'current_volume' in volume_data and 'historical_volumes' in volume_data:
                factors['volume_ratio'] = VolumeFactors.calculate_volume_ratio(
                    volume_data['current_volume'],
                    volume_data['historical_volumes'],
                    ratio_window
                )
            
            # Volume spike score
            if 'historical_volumes' in volume_data:
                all_volumes = volume_data['historical_volumes'] + [volume_data.get('current_volume', 0)]
                factors['volume_spike_score'] = VolumeFactors.calculate_volume_spike_score(
                    all_volumes,
                    ratio_window
                )
            
            # Volume trend
            if 'historical_volumes' in volume_data:
                all_volumes = volume_data['historical_volumes'] + [volume_data.get('current_volume', 0)]
                factors['volume_trend'] = VolumeFactors.calculate_volume_trend(all_volumes)
            
            # Buy/sell ratio
            if 'taker_buy_volume' in volume_data and 'current_volume' in volume_data:
                factors['buy_sell_ratio'] = VolumeFactors.calculate_buy_sell_ratio(
                    volume_data['taker_buy_volume'],
                    volume_data['current_volume']
                )
            
            # Large trade ratio
            if 'trade_volumes' in volume_data:
                factors['large_trade_ratio'] = VolumeFactors.calculate_large_trade_ratio(
                    volume_data['trade_volumes']
                )
            
            return factors
        
        except Exception as e:
            logger.error(f"Error calculating volume factors: {e}")
            return {}


if __name__ == "__main__":
    # Test volume factors
    logger.add("logs/factors.log")
    
    # Simulate normal volumes
    historical_volumes = [100 + np.random.normal(0, 10) for _ in range(60)]
    
    # Simulate volume spike
    current_volume = 350  # 3.5x average
    
    volume_data = {
        'current_volume': current_volume,
        'historical_volumes': historical_volumes,
        'taker_buy_volume': current_volume * 0.7,  # 70% buy pressure
        'trade_volumes': [10, 15, 8, 50, 12, 200, 9]  # Some large trades
    }
    
    config = {
        'ratio_window': 60
    }
    
    factors = VolumeFactors.calculate_all(volume_data, config)
    
    print("\n?? Volume Factors:")
    for key, value in factors.items():
        print(f"  {key}: {value:.4f}")
    
    if 'volume_spike_score' in factors:
        score = factors['volume_spike_score']
        print(f"\n{'??' if score > 0.7 else '??'} Volume Spike Score: {score:.4f}")
