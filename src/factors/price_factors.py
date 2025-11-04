"""
Price-based factor calculations
"""

import numpy as np
from typing import List, Dict
from loguru import logger


class PriceFactors:
    """Calculate price-related factors for pump & dump detection"""
    
    @staticmethod
    def calculate_velocity(prices: List[float], window: int) -> float:
        """
        Calculate price velocity (rate of change)
        
        Args:
            prices: List of prices (most recent last)
            window: Time window (in number of periods)
            
        Returns:
            Price velocity as percentage
        """
        if len(prices) < window + 1:
            return 0.0
        
        current_price = prices[-1]
        past_price = prices[-window-1]
        
        if past_price == 0:
            return 0.0
        
        velocity = (current_price - past_price) / past_price * 100
        return velocity
    
    @staticmethod
    def calculate_acceleration(velocities: List[float]) -> float:
        """
        Calculate price acceleration (change in velocity)
        
        Args:
            velocities: List of velocity values
            
        Returns:
            Acceleration value
        """
        if len(velocities) < 2:
            return 0.0
        
        current_velocity = velocities[-1]
        past_velocity = velocities[-2]
        
        acceleration = current_velocity - past_velocity
        return acceleration
    
    @staticmethod
    def calculate_volatility(prices: List[float], window: int = 15) -> float:
        """
        Calculate price volatility (standard deviation of returns)
        
        Args:
            prices: List of prices
            window: Calculation window
            
        Returns:
            Volatility as percentage
        """
        if len(prices) < window + 1:
            return 0.0
        
        recent_prices = prices[-window-1:]
        returns = np.diff(recent_prices) / recent_prices[:-1]
        
        volatility = np.std(returns) * 100
        return float(volatility)
    
    @staticmethod
    def check_breakout(current_price: float, high: float, low: float) -> Dict[str, bool]:
        """
        Check if price breaks out of recent range
        
        Args:
            current_price: Current price
            high: Recent high
            low: Recent low
            
        Returns:
            Dict with breakout_up and breakout_down flags
        """
        return {
            'breakout_up': current_price > high,
            'breakout_down': current_price < low
        }
    
    @staticmethod
    def calculate_price_position(current_price: float, high: float, low: float) -> float:
        """
        Calculate relative price position in recent range
        
        Args:
            current_price: Current price
            high: Recent high
            low: Recent low
            
        Returns:
            Position value (0-1), where 0=lowest, 1=highest
        """
        if high == low:
            return 0.5
        
        position = (current_price - low) / (high - low)
        return max(0.0, min(1.0, position))
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """
        Calculate Relative Strength Index
        
        Args:
            prices: List of prices
            period: RSI period (default 14)
            
        Returns:
            RSI value (0-100)
        """
        if len(prices) < period + 1:
            return 50.0  # Neutral value
        
        recent_prices = prices[-period-1:]
        deltas = np.diff(recent_prices)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    @staticmethod
    def calculate_all(prices: List[float], config: dict) -> Dict[str, float]:
        """
        Calculate all price factors
        
        Args:
            prices: List of prices (chronological order, most recent last)
            config: Configuration dict with windows and parameters
            
        Returns:
            Dict of all calculated factors
        """
        if len(prices) < 2:
            return {}
        
        try:
            # Get windows from config
            velocity_windows = config.get('velocity_windows', [1, 5, 15])
            volatility_window = config.get('volatility_window', 15)
            breakout_window = config.get('breakout_window', 15)
            rsi_period = config.get('rsi_period', 14)
            
            factors = {}
            
            # Calculate velocities for different windows
            velocities = []
            for window in velocity_windows:
                velocity = PriceFactors.calculate_velocity(prices, window)
                factors[f'price_velocity_{window}m'] = velocity
                velocities.append(velocity)
            
            # Calculate acceleration
            if len(velocities) >= 2:
                factors['price_acceleration'] = PriceFactors.calculate_acceleration(velocities)
            
            # Calculate volatility
            factors['price_volatility'] = PriceFactors.calculate_volatility(prices, volatility_window)
            
            # Check breakouts
            if len(prices) >= breakout_window:
                recent_prices = prices[-breakout_window:]
                high = max(recent_prices[:-1])  # Exclude current price
                low = min(recent_prices[:-1])
                current_price = prices[-1]
                
                breakout = PriceFactors.check_breakout(current_price, high, low)
                factors['breakout_up'] = 1.0 if breakout['breakout_up'] else 0.0
                factors['breakout_down'] = 1.0 if breakout['breakout_down'] else 0.0
                
                factors['price_position'] = PriceFactors.calculate_price_position(
                    current_price, high, low
                )
            
            # Calculate RSI
            factors['rsi'] = PriceFactors.calculate_rsi(prices, rsi_period)
            
            return factors
        
        except Exception as e:
            logger.error(f"Error calculating price factors: {e}")
            return {}


if __name__ == "__main__":
    # Test price factors
    logger.add("logs/factors.log")
    
    # Simulate price data with a pump
    base_price = 100.0
    prices = []
    
    # Normal prices
    for i in range(50):
        prices.append(base_price + np.random.normal(0, 1))
    
    # Pump!
    for i in range(10):
        prices.append(prices[-1] * 1.03)  # 3% increase each period
    
    config = {
        'velocity_windows': [1, 5, 15],
        'volatility_window': 15,
        'breakout_window': 15,
        'rsi_period': 14
    }
    
    factors = PriceFactors.calculate_all(prices, config)
    
    print("\n?? Price Factors:")
    for key, value in factors.items():
        print(f"  {key}: {value:.4f}")
    
    print(f"\n?? Velocity (5m): {factors.get('price_velocity_5m', 0):.2f}%")
    print(f"?? RSI: {factors.get('rsi', 0):.2f}")
