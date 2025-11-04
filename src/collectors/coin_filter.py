"""
Coin filtering logic to select coins for monitoring
"""

from binance.client import Client
from typing import List, Dict
from loguru import logger
import yaml
from datetime import datetime, timedelta


class CoinFilter:
    """Filter and select coins for pump & dump monitoring"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize coin filter
        
        Args:
            config_path: Path to configuration file
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.filters = config['data_collection']['coin_filters']
        self.quote_currency = config['data_collection']['quote_currency']
        
        self.min_market_cap = self.filters['min_market_cap']
        self.max_market_cap = self.filters['max_market_cap']
        self.min_24h_volume = self.filters['min_24h_volume']
        self.max_listing_age_days = self.filters.get('max_listing_age_days', 90)
        self.exclude_stable_coins = self.filters.get('exclude_stable_coins', True)
        self.exclude_wrapped_tokens = self.filters.get('exclude_wrapped_tokens', True)
        
        # Stable coins and wrapped tokens to exclude
        self.stable_coin_keywords = ['USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDD', 'USDP', 'FDUSD']
        self.wrapped_keywords = ['WBTC', 'WETH', 'WBNB']
        
        logger.info(f"CoinFilter initialized with:")
        logger.info(f"  Market cap range: ${self.min_market_cap:,} - ${self.max_market_cap:,}")
        logger.info(f"  Min 24h volume: ${self.min_24h_volume:,}")
        logger.info(f"  Max listing age: {self.max_listing_age_days} days")
    
    def get_filtered_coins(self, client: Client) -> List[str]:
        """
        Get list of coins that match filtering criteria
        
        Args:
            client: Binance API client
            
        Returns:
            List of coin symbols (e.g., ['BTCUSDT', 'ETHUSDT', ...])
        """
        logger.info("Fetching and filtering coins...")
        
        # Get all trading pairs
        exchange_info = client.get_exchange_info()
        all_symbols = [s for s in exchange_info['symbols'] 
                      if s['quoteAsset'] == self.quote_currency and s['status'] == 'TRADING']
        
        logger.info(f"Found {len(all_symbols)} {self.quote_currency} pairs")
        
        # Get 24h ticker data
        tickers = client.get_ticker()
        ticker_dict = {t['symbol']: t for t in tickers}
        
        # Filter coins
        filtered_coins = []
        
        for symbol_info in all_symbols:
            symbol = symbol_info['symbol']
            
            # Skip if no ticker data
            if symbol not in ticker_dict:
                continue
            
            ticker = ticker_dict[symbol]
            
            # Apply filters
            if not self._passes_filters(symbol, ticker, symbol_info):
                continue
            
            filtered_coins.append(symbol)
        
        logger.info(f"? Filtered to {len(filtered_coins)} coins for monitoring")
        logger.info(f"Top coins: {filtered_coins[:10]}")
        
        return filtered_coins
    
    def _passes_filters(self, symbol: str, ticker: Dict, symbol_info: Dict) -> bool:
        """
        Check if a coin passes all filters
        
        Args:
            symbol: Trading pair symbol
            ticker: 24h ticker data
            symbol_info: Exchange info for the symbol
            
        Returns:
            True if passes all filters
        """
        # 1. Exclude stable coins
        if self.exclude_stable_coins:
            if any(stable in symbol for stable in self.stable_coin_keywords):
                return False
        
        # 2. Exclude wrapped tokens
        if self.exclude_wrapped_tokens:
            if any(wrapped in symbol for wrapped in self.wrapped_keywords):
                return False
        
        # 3. Check 24h volume
        try:
            quote_volume = float(ticker.get('quoteVolume', 0))
            if quote_volume < self.min_24h_volume:
                return False
        except (ValueError, TypeError):
            return False
        
        # 4. Check price (filter out extremely low price coins - often scams)
        try:
            price = float(ticker.get('lastPrice', 0))
            if price < 0.0001:  # Less than $0.0001
                return False
        except (ValueError, TypeError):
            return False
        
        # 5. Estimate market cap (simplified: quote_volume as proxy)
        # Note: For accurate market cap, need external API (CoinGecko/CMC)
        # Here we use 24h volume as a rough indicator of liquidity
        # Actual implementation should fetch real market cap data
        
        return True
    
    def filter_by_priority(self, symbols: List[str], client: Client, top_n: int = 50) -> List[str]:
        """
        Sort and filter coins by priority (higher manipulation risk = higher priority)
        
        Args:
            symbols: List of symbols to prioritize
            client: Binance API client
            top_n: Number of top coins to return
            
        Returns:
            Top N symbols sorted by priority
        """
        tickers = client.get_ticker()
        ticker_dict = {t['symbol']: t for t in tickers if t['symbol'] in symbols}
        
        priority_scores = []
        
        for symbol in symbols:
            if symbol not in ticker_dict:
                continue
            
            ticker = ticker_dict[symbol]
            
            # Calculate priority score
            # Higher score = higher priority for monitoring
            score = self._calculate_priority_score(ticker)
            
            priority_scores.append((symbol, score))
        
        # Sort by score (descending)
        priority_scores.sort(key=lambda x: x[1], reverse=True)
        
        top_symbols = [s for s, _ in priority_scores[:top_n]]
        
        logger.info(f"Prioritized top {len(top_symbols)} coins for monitoring")
        return top_symbols
    
    def _calculate_priority_score(self, ticker: Dict) -> float:
        """
        Calculate priority score for a coin
        
        Factors:
        - Lower market cap = higher score (easier to manipulate)
        - High recent volume spike = higher score
        - High price volatility = higher score
        
        Args:
            ticker: 24h ticker data
            
        Returns:
            Priority score (higher = more important to monitor)
        """
        score = 0.0
        
        try:
            # Factor 1: Volume (use as market cap proxy)
            quote_volume = float(ticker.get('quoteVolume', 0))
            if quote_volume > 0:
                # Inverse relationship: lower volume = higher score
                volume_score = 1000000 / quote_volume  # Normalize
                score += volume_score * 0.4
            
            # Factor 2: Price change
            price_change_pct = float(ticker.get('priceChangePercent', 0))
            volatility_score = abs(price_change_pct)
            score += volatility_score * 0.3
            
            # Factor 3: Number of trades
            count = int(ticker.get('count', 0))
            if count > 0:
                trade_intensity = count / 86400  # trades per second
                score += min(trade_intensity * 100, 10) * 0.3  # Cap at 10
        
        except (ValueError, TypeError):
            pass
        
        return score


if __name__ == "__main__":
    # Test coin filtering
    from binance.client import Client
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    logger.add("logs/coin_filter.log")
    
    api_key = os.getenv('BINANCE_API_KEY', '')
    api_secret = os.getenv('BINANCE_API_SECRET', '')
    
    client = Client(api_key, api_secret)
    
    coin_filter = CoinFilter()
    filtered_coins = coin_filter.get_filtered_coins(client)
    
    print(f"\nFiltered coins: {len(filtered_coins)}")
    print(f"Sample: {filtered_coins[:20]}")
    
    # Get top priority
    top_coins = coin_filter.filter_by_priority(filtered_coins, client, top_n=20)
    print(f"\nTop 20 priority coins:")
    for i, coin in enumerate(top_coins, 1):
        print(f"{i}. {coin}")
