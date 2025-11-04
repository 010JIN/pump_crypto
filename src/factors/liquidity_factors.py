"""
Liquidity-based factor calculations
"""

import numpy as np
from typing import List, Dict, Tuple
from loguru import logger


class LiquidityFactors:
    """Calculate liquidity-related factors from order book data"""
    
    @staticmethod
    def calculate_bid_ask_imbalance(bids: List[Tuple[float, float]], 
                                     asks: List[Tuple[float, float]], 
                                     depth: int = 10) -> float:
        """
        Calculate bid-ask imbalance
        
        Args:
            bids: List of [price, quantity] for bids
            asks: List of [price, quantity] for asks
            depth: Number of levels to consider
            
        Returns:
            Imbalance value (-1 to 1), positive = more buy pressure
        """
        if not bids or not asks:
            return 0.0
        
        # Sum volumes for top N levels
        bid_volume = sum([q for p, q in bids[:depth]])
        ask_volume = sum([q for p, q in asks[:depth]])
        
        total_volume = bid_volume + ask_volume
        
        if total_volume == 0:
            return 0.0
        
        imbalance = (bid_volume - ask_volume) / total_volume
        return float(imbalance)
    
    @staticmethod
    def calculate_liquidity_score(bids: List[Tuple[float, float]], 
                                   asks: List[Tuple[float, float]], 
                                   current_price: float,
                                   price_range_pct: float = 2.0) -> float:
        """
        Calculate liquidity score within a price range
        
        Args:
            bids: List of [price, quantity] for bids
            asks: List of [price, quantity] for asks
            current_price: Current market price
            price_range_pct: Price range percentage (default 2%)
            
        Returns:
            Total liquidity within range
        """
        if not bids or not asks or current_price == 0:
            return 0.0
        
        price_range = current_price * (price_range_pct / 100)
        
        # Count liquidity within range
        bid_liquidity = sum([q for p, q in bids if p >= current_price - price_range])
        ask_liquidity = sum([q for p, q in asks if p <= current_price + price_range])
        
        total_liquidity = bid_liquidity + ask_liquidity
        return float(total_liquidity)
    
    @staticmethod
    def calculate_spread(bids: List[Tuple[float, float]], 
                        asks: List[Tuple[float, float]]) -> Dict[str, float]:
        """
        Calculate bid-ask spread
        
        Args:
            bids: List of [price, quantity] for bids
            asks: List of [price, quantity] for asks
            
        Returns:
            Dict with absolute and percentage spread
        """
        if not bids or not asks:
            return {'spread': 0.0, 'spread_percent': 0.0}
        
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        
        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2
        
        if mid_price == 0:
            spread_percent = 0.0
        else:
            spread_percent = (spread / mid_price) * 100
        
        return {
            'spread': float(spread),
            'spread_percent': float(spread_percent)
        }
    
    @staticmethod
    def calculate_orderbook_pressure(bids: List[Tuple[float, float]], 
                                     asks: List[Tuple[float, float]], 
                                     levels: int = 5) -> float:
        """
        Calculate weighted order book pressure across multiple levels
        
        Args:
            bids: List of [price, quantity] for bids
            asks: List of [price, quantity] for asks
            levels: Number of levels to analyze
            
        Returns:
            Pressure value (-1 to 1)
        """
        if not bids or not asks:
            return 0.0
        
        # Weights for each level (closer levels have more weight)
        weights = [0.4, 0.3, 0.2, 0.07, 0.03][:levels]
        
        pressures = []
        
        for i in range(min(levels, len(bids), len(asks))):
            bid_volume = bids[i][1]
            ask_volume = asks[i][1]
            
            total = bid_volume + ask_volume
            if total == 0:
                pressure = 0.0
            else:
                pressure = (bid_volume - ask_volume) / total
            
            pressures.append(pressure)
        
        # Calculate weighted average
        if not pressures:
            return 0.0
        
        # Adjust weights if we have fewer levels
        weights = weights[:len(pressures)]
        weighted_pressure = sum([p * w for p, w in zip(pressures, weights)])
        
        return float(weighted_pressure)
    
    @staticmethod
    def calculate_depth_imbalance_by_distance(bids: List[Tuple[float, float]], 
                                              asks: List[Tuple[float, float]], 
                                              current_price: float) -> float:
        """
        Calculate depth imbalance weighted by distance from current price
        
        Args:
            bids: List of [price, quantity] for bids
            asks: List of [price, quantity] for asks
            current_price: Current market price
            
        Returns:
            Weighted imbalance value
        """
        if not bids or not asks or current_price == 0:
            return 0.0
        
        weighted_bid_volume = 0.0
        weighted_ask_volume = 0.0
        
        # Weight by inverse distance
        for bid_price, bid_qty in bids:
            distance = abs(current_price - bid_price) / current_price
            if distance == 0:
                weight = 1.0
            else:
                weight = 1.0 / (1.0 + distance * 100)  # Decay function
            weighted_bid_volume += bid_qty * weight
        
        for ask_price, ask_qty in asks:
            distance = abs(ask_price - current_price) / current_price
            if distance == 0:
                weight = 1.0
            else:
                weight = 1.0 / (1.0 + distance * 100)
            weighted_ask_volume += ask_qty * weight
        
        total = weighted_bid_volume + weighted_ask_volume
        if total == 0:
            return 0.0
        
        imbalance = (weighted_bid_volume - weighted_ask_volume) / total
        return float(imbalance)
    
    @staticmethod
    def calculate_all(orderbook_data: Dict, current_price: float, config: dict) -> Dict[str, float]:
        """
        Calculate all liquidity factors
        
        Args:
            orderbook_data: Dict containing 'bids' and 'asks'
            current_price: Current market price
            config: Configuration dict
            
        Returns:
            Dict of all calculated factors
        """
        try:
            bids = orderbook_data.get('bids', [])
            asks = orderbook_data.get('asks', [])
            
            if not bids or not asks:
                return {}
            
            factors = {}
            
            # Bid-ask imbalance
            depth_levels = config.get('orderbook_depth_levels', 10)
            factors['bid_ask_imbalance'] = LiquidityFactors.calculate_bid_ask_imbalance(
                bids, asks, depth_levels
            )
            
            # Liquidity score
            factors['liquidity_score'] = LiquidityFactors.calculate_liquidity_score(
                bids, asks, current_price
            )
            
            # Spread
            spread_data = LiquidityFactors.calculate_spread(bids, asks)
            factors.update(spread_data)
            
            # Order book pressure
            factors['orderbook_pressure'] = LiquidityFactors.calculate_orderbook_pressure(
                bids, asks, levels=5
            )
            
            # Distance-weighted imbalance
            factors['depth_imbalance_weighted'] = LiquidityFactors.calculate_depth_imbalance_by_distance(
                bids, asks, current_price
            )
            
            return factors
        
        except Exception as e:
            logger.error(f"Error calculating liquidity factors: {e}")
            return {}


if __name__ == "__main__":
    # Test liquidity factors
    logger.add("logs/factors.log")
    
    # Simulate order book with buy pressure
    current_price = 100.0
    
    bids = [
        [99.5, 10.0],
        [99.0, 15.0],
        [98.5, 8.0],
        [98.0, 12.0],
        [97.5, 20.0],
    ]
    
    asks = [
        [100.5, 5.0],   # Less sell pressure
        [101.0, 7.0],
        [101.5, 4.0],
        [102.0, 6.0],
        [102.5, 3.0],
    ]
    
    orderbook_data = {
        'bids': bids,
        'asks': asks
    }
    
    config = {
        'orderbook_depth_levels': 10
    }
    
    factors = LiquidityFactors.calculate_all(orderbook_data, current_price, config)
    
    print("\n?? Liquidity Factors:")
    for key, value in factors.items():
        print(f"  {key}: {value:.4f}")
    
    if 'bid_ask_imbalance' in factors:
        imbalance = factors['bid_ask_imbalance']
        if imbalance > 0.3:
            print(f"\n?? Strong buy pressure detected: {imbalance:.4f}")
        elif imbalance < -0.3:
            print(f"\n?? Strong sell pressure detected: {imbalance:.4f}")
