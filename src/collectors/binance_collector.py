"""
Binance WebSocket data collector
Collects real-time price, kline, trade, and orderbook data
"""

import asyncio
import json
import websockets
from binance.client import Client
from binance import AsyncClient, BinanceSocketManager
from typing import List, Callable, Optional, Dict
from datetime import datetime
from loguru import logger
import time


class BinanceCollector:
    """
    Real-time data collector for Binance
    Uses WebSocket to stream market data
    """
    
    def __init__(self, symbols: List[str], callbacks: Dict[str, Callable] = None):
        """
        Initialize Binance collector
        
        Args:
            symbols: List of symbols to monitor (e.g., ['BTCUSDT', 'ETHUSDT'])
            callbacks: Dict of callback functions for different data types
                      {
                          'ticker': func(data),
                          'kline': func(data),
                          'trade': func(data),
                          'depth': func(data)
                      }
        """
        self.symbols = [s.lower() for s in symbols]
        self.callbacks = callbacks or {}
        self.client: Optional[AsyncClient] = None
        self.bsm: Optional[BinanceSocketManager] = None
        self.tasks = []
        self.is_running = False
        
        logger.info(f"BinanceCollector initialized for {len(self.symbols)} symbols")
    
    async def start(self):
        """Start collecting data"""
        if self.is_running:
            logger.warning("Collector is already running")
            return
        
        self.is_running = True
        logger.info("?? Starting BinanceCollector...")
        
        # Initialize async client
        self.client = await AsyncClient.create()
        self.bsm = BinanceSocketManager(self.client)
        
        # Start WebSocket streams
        await self._start_streams()
        
        logger.info("? BinanceCollector started successfully")
    
    async def stop(self):
        """Stop collecting data"""
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("Stopping BinanceCollector...")
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Close connections
        if self.bsm:
            await self.bsm.close()
        if self.client:
            await self.client.close_connection()
        
        logger.info("BinanceCollector stopped")
    
    async def _start_streams(self):
        """Start all WebSocket streams"""
        # For each symbol, start multiple streams
        for symbol in self.symbols:
            # 1. Ticker stream (24h statistics)
            if 'ticker' in self.callbacks:
                task = asyncio.create_task(self._ticker_stream(symbol))
                self.tasks.append(task)
            
            # 2. Kline stream (1m candlesticks)
            if 'kline' in self.callbacks:
                task = asyncio.create_task(self._kline_stream(symbol, '1m'))
                self.tasks.append(task)
            
            # 3. Trade stream (individual trades)
            if 'trade' in self.callbacks:
                task = asyncio.create_task(self._trade_stream(symbol))
                self.tasks.append(task)
            
            # 4. Depth stream (order book)
            if 'depth' in self.callbacks:
                task = asyncio.create_task(self._depth_stream(symbol))
                self.tasks.append(task)
        
        logger.info(f"Started {len(self.tasks)} WebSocket streams")
    
    async def _ticker_stream(self, symbol: str):
        """Stream 24h ticker data"""
        stream_name = f"{symbol}@ticker"
        
        while self.is_running:
            try:
                async with self.bsm.symbol_ticker_socket(symbol) as stream:
                    while self.is_running:
                        msg = await stream.recv()
                        
                        if msg:
                            # Parse ticker data
                            data = {
                                'symbol': msg['s'],
                                'price': float(msg['c']),
                                'price_change': float(msg['p']),
                                'price_change_percent': float(msg['P']),
                                'weighted_avg_price': float(msg['w']),
                                'volume': float(msg['v']),
                                'quote_volume': float(msg['q']),
                                'open': float(msg['o']),
                                'high': float(msg['h']),
                                'low': float(msg['l']),
                                'timestamp': datetime.fromtimestamp(msg['E'] / 1000)
                            }
                            
                            # Call callback
                            if 'ticker' in self.callbacks:
                                await self.callbacks['ticker'](data)
            
            except Exception as e:
                logger.error(f"Error in ticker stream for {symbol}: {e}")
                await asyncio.sleep(5)  # Wait before reconnecting
    
    async def _kline_stream(self, symbol: str, interval: str):
        """Stream kline (candlestick) data"""
        while self.is_running:
            try:
                async with self.bsm.kline_socket(symbol, interval) as stream:
                    while self.is_running:
                        msg = await stream.recv()
                        
                        if msg and msg['e'] == 'kline':
                            kline = msg['k']
                            
                            # Only process closed candles
                            if not kline['x']:  # x = is_closed
                                continue
                            
                            data = {
                                'symbol': kline['s'],
                                'interval': kline['i'],
                                'open_time': datetime.fromtimestamp(kline['t'] / 1000),
                                'close_time': datetime.fromtimestamp(kline['T'] / 1000),
                                'open': float(kline['o']),
                                'high': float(kline['h']),
                                'low': float(kline['l']),
                                'close': float(kline['c']),
                                'volume': float(kline['v']),
                                'quote_volume': float(kline['q']),
                                'trades': int(kline['n']),
                                'taker_buy_volume': float(kline['V']),
                                'taker_buy_quote_volume': float(kline['Q'])
                            }
                            
                            # Call callback
                            if 'kline' in self.callbacks:
                                await self.callbacks['kline'](data)
            
            except Exception as e:
                logger.error(f"Error in kline stream for {symbol}: {e}")
                await asyncio.sleep(5)
    
    async def _trade_stream(self, symbol: str):
        """Stream individual trade data"""
        while self.is_running:
            try:
                async with self.bsm.trade_socket(symbol) as stream:
                    while self.is_running:
                        msg = await stream.recv()
                        
                        if msg:
                            data = {
                                'symbol': msg['s'],
                                'trade_id': msg['t'],
                                'price': float(msg['p']),
                                'quantity': float(msg['q']),
                                'buyer_maker': msg['m'],  # True if buyer is maker
                                'timestamp': datetime.fromtimestamp(msg['T'] / 1000)
                            }
                            
                            # Call callback
                            if 'trade' in self.callbacks:
                                await self.callbacks['trade'](data)
            
            except Exception as e:
                logger.error(f"Error in trade stream for {symbol}: {e}")
                await asyncio.sleep(5)
    
    async def _depth_stream(self, symbol: str):
        """Stream order book depth data"""
        while self.is_running:
            try:
                async with self.bsm.depth_socket(symbol, depth='20') as stream:
                    while self.is_running:
                        msg = await stream.recv()
                        
                        if msg:
                            data = {
                                'symbol': symbol.upper(),
                                'bids': [[float(p), float(q)] for p, q in msg['bids']],
                                'asks': [[float(p), float(q)] for p, q in msg['asks']],
                                'timestamp': datetime.now()
                            }
                            
                            # Call callback
                            if 'depth' in self.callbacks:
                                await self.callbacks['depth'](data)
            
            except Exception as e:
                logger.error(f"Error in depth stream for {symbol}: {e}")
                await asyncio.sleep(5)


class DataAggregator:
    """
    Aggregates streaming data for storage and analysis
    """
    
    def __init__(self, postgres_manager, redis_manager):
        """
        Initialize data aggregator
        
        Args:
            postgres_manager: PostgreSQL manager instance
            redis_manager: Redis manager instance
        """
        self.pg = postgres_manager
        self.redis = redis_manager
        
        # Buffers for batch writing
        self.ticker_buffer = []
        self.kline_buffer = []
        self.trade_buffer = {}  # {symbol: [trades]}
        self.depth_buffer = []
        
        self.buffer_size = 100
        self.last_flush_time = time.time()
        
        logger.info("DataAggregator initialized")
    
    async def on_ticker(self, data: dict):
        """Handle ticker data"""
        symbol = data['symbol']
        
        # Cache in Redis
        self.redis.set_price(
            symbol,
            data['price'],
            int(data['timestamp'].timestamp())
        )
        
        # Buffer for batch insert
        self.ticker_buffer.append(data)
        
        # Flush if buffer is full
        if len(self.ticker_buffer) >= self.buffer_size:
            await self._flush_tickers()
        
        logger.debug(f"Ticker: {symbol} = ${data['price']:.4f} ({data['price_change_percent']:+.2f}%)")
    
    async def on_kline(self, data: dict):
        """Handle kline data"""
        symbol = data['symbol']
        interval = data['interval']
        
        # Cache in Redis
        self.redis.push_kline(symbol, interval, data)
        
        # Buffer for database
        self.kline_buffer.append(data)
        
        if len(self.kline_buffer) >= self.buffer_size:
            await self._flush_klines()
        
        logger.debug(f"Kline: {symbol} {interval} | O:{data['open']:.4f} H:{data['high']:.4f} L:{data['low']:.4f} C:{data['close']:.4f}")
    
    async def on_trade(self, data: dict):
        """Handle trade data"""
        symbol = data['symbol']
        
        # Aggregate trades per minute
        if symbol not in self.trade_buffer:
            self.trade_buffer[symbol] = []
        
        self.trade_buffer[symbol].append(data)
        
        # Periodically aggregate and flush
        current_time = time.time()
        if current_time - self.last_flush_time >= 60:  # Every minute
            await self._flush_trades()
            self.last_flush_time = current_time
    
    async def on_depth(self, data: dict):
        """Handle order book depth data"""
        symbol = data['symbol']
        
        # Calculate metrics
        bids = data['bids']
        asks = data['asks']
        
        bid_total = sum([q for p, q in bids])
        ask_total = sum([q for p, q in asks])
        
        if bid_total + ask_total > 0:
            bid_ask_ratio = bid_total / (bid_total + ask_total)
        else:
            bid_ask_ratio = 0.5
        
        top_bid = bids[0][0] if bids else 0
        top_ask = asks[0][0] if asks else 0
        
        if top_bid > 0 and top_ask > 0:
            spread = top_ask - top_bid
            mid_price = (top_bid + top_ask) / 2
            spread_percent = (spread / mid_price) * 100 if mid_price > 0 else 0
        else:
            spread = 0
            spread_percent = 0
        
        # Cache in Redis
        orderbook_data = {
            'bids': json.dumps(bids),
            'asks': json.dumps(asks),
            'timestamp': str(data['timestamp'])
        }
        self.redis.set_orderbook(symbol, orderbook_data)
        
        # Prepare for database
        depth_data = {
            'symbol': symbol,
            'timestamp': data['timestamp'],
            'bid_total_volume': bid_total,
            'ask_total_volume': ask_total,
            'bid_ask_ratio': bid_ask_ratio,
            'spread': spread,
            'spread_percent': spread_percent,
            'top_bid_price': top_bid,
            'top_ask_price': top_ask
        }
        
        self.depth_buffer.append(depth_data)
        
        if len(self.depth_buffer) >= self.buffer_size:
            await self._flush_depth()
    
    async def _flush_tickers(self):
        """Flush ticker buffer to database"""
        if not self.ticker_buffer:
            return
        
        try:
            from src.storage import Ticker
            
            with self.pg.session_scope() as session:
                for data in self.ticker_buffer:
                    ticker = Ticker(**data)
                    session.add(ticker)
            
            logger.debug(f"Flushed {len(self.ticker_buffer)} tickers to database")
            self.ticker_buffer.clear()
        
        except Exception as e:
            logger.error(f"Error flushing tickers: {e}")
    
    async def _flush_klines(self):
        """Flush kline buffer to database"""
        if not self.kline_buffer:
            return
        
        try:
            from src.storage import Kline
            
            with self.pg.session_scope() as session:
                for data in self.kline_buffer:
                    kline = Kline(**data)
                    session.merge(kline)  # Use merge to handle duplicates
            
            logger.debug(f"Flushed {len(self.kline_buffer)} klines to database")
            self.kline_buffer.clear()
        
        except Exception as e:
            logger.error(f"Error flushing klines: {e}")
    
    async def _flush_trades(self):
        """Aggregate and flush trade data"""
        if not self.trade_buffer:
            return
        
        try:
            from src.storage import TradeAggregated
            
            with self.pg.session_scope() as session:
                for symbol, trades in self.trade_buffer.items():
                    if not trades:
                        continue
                    
                    # Get minute timestamp
                    minute_time = trades[0]['timestamp'].replace(second=0, microsecond=0)
                    
                    # Aggregate
                    total_volume = sum([t['quantity'] for t in trades])
                    buy_volume = sum([t['quantity'] for t in trades if not t['buyer_maker']])
                    sell_volume = total_volume - buy_volume
                    total_trades = len(trades)
                    
                    # Identify large trades
                    avg_volume = total_volume / total_trades if total_trades > 0 else 0
                    large_trades = len([t for t in trades if t['quantity'] > avg_volume * 3])
                    
                    avg_price = sum([t['price'] * t['quantity'] for t in trades]) / total_volume if total_volume > 0 else 0
                    
                    trade_agg = TradeAggregated(
                        symbol=symbol,
                        minute_time=minute_time,
                        total_volume=total_volume,
                        buy_volume=buy_volume,
                        sell_volume=sell_volume,
                        total_trades=total_trades,
                        large_trades=large_trades,
                        avg_price=avg_price
                    )
                    session.merge(trade_agg)
            
            logger.debug(f"Flushed aggregated trades for {len(self.trade_buffer)} symbols")
            self.trade_buffer.clear()
        
        except Exception as e:
            logger.error(f"Error flushing trades: {e}")
    
    async def _flush_depth(self):
        """Flush order book depth data"""
        if not self.depth_buffer:
            return
        
        try:
            from src.storage import OrderbookSnapshot
            
            with self.pg.session_scope() as session:
                for data in self.depth_buffer:
                    snapshot = OrderbookSnapshot(**data)
                    session.add(snapshot)
            
            logger.debug(f"Flushed {len(self.depth_buffer)} depth snapshots to database")
            self.depth_buffer.clear()
        
        except Exception as e:
            logger.error(f"Error flushing depth data: {e}")


if __name__ == "__main__":
    # Test data collection
    import os
    from dotenv import load_dotenv
    from src.storage import init_databases
    
    load_dotenv()
    logger.add("logs/collector.log", rotation="100 MB")
    
    async def main():
        # Initialize databases
        pg, redis = init_databases()
        
        # Create aggregator
        aggregator = DataAggregator(pg, redis)
        
        # Create collector
        test_symbols = ['BTCUSDT', 'ETHUSDT']
        
        callbacks = {
            'ticker': aggregator.on_ticker,
            'kline': aggregator.on_kline,
            'trade': aggregator.on_trade,
            'depth': aggregator.on_depth
        }
        
        collector = BinanceCollector(test_symbols, callbacks)
        
        # Start collecting
        await collector.start()
        
        # Run for 60 seconds
        print("Collecting data for 60 seconds...")
        await asyncio.sleep(60)
        
        # Stop
        await collector.stop()
        print("Collection stopped")
    
    asyncio.run(main())
