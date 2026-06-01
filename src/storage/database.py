"""
Database connection and schema management
Handles PostgreSQL and Redis connections
"""

from sqlalchemy import create_engine, Column, Integer, String, DECIMAL, TIMESTAMP, BigInteger, Index, UniqueConstraint, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from contextlib import contextmanager
import redis
from typing import Optional
import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

Base = declarative_base()


# ==================== PostgreSQL Models ====================

class Kline(Base):
    """K-line (OHLCV) data table"""
    __tablename__ = 'klines'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    interval = Column(String(5), nullable=False)  # 1m, 5m, 15m
    open_time = Column(TIMESTAMP, nullable=False)
    close_time = Column(TIMESTAMP, nullable=False)
    open = Column(DECIMAL(20, 8), nullable=False)
    high = Column(DECIMAL(20, 8), nullable=False)
    low = Column(DECIMAL(20, 8), nullable=False)
    close = Column(DECIMAL(20, 8), nullable=False)
    volume = Column(DECIMAL(20, 8), nullable=False)
    quote_volume = Column(DECIMAL(20, 8), nullable=False)
    trades = Column(Integer)
    taker_buy_volume = Column(DECIMAL(20, 8))
    taker_buy_quote_volume = Column(DECIMAL(20, 8))
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    
    __table_args__ = (
        UniqueConstraint('symbol', 'interval', 'open_time', name='uq_kline'),
        Index('idx_klines_symbol_time', 'symbol', 'open_time'),
    )


class Ticker(Base):
    """Real-time ticker data"""
    __tablename__ = 'tickers'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    price = Column(DECIMAL(20, 8), nullable=False)
    price_change = Column(DECIMAL(20, 8))
    price_change_percent = Column(DECIMAL(10, 4))
    volume = Column(DECIMAL(20, 8))
    quote_volume = Column(DECIMAL(20, 8))
    timestamp = Column(TIMESTAMP, nullable=False, index=True)
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    
    __table_args__ = (
        Index('idx_tickers_symbol_time', 'symbol', 'timestamp'),
    )


class TradeAggregated(Base):
    """Aggregated trade data (per minute)"""
    __tablename__ = 'trades_aggregated'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    minute_time = Column(TIMESTAMP, nullable=False)
    total_volume = Column(DECIMAL(20, 8))
    buy_volume = Column(DECIMAL(20, 8))
    sell_volume = Column(DECIMAL(20, 8))
    total_trades = Column(Integer)
    large_trades = Column(Integer)
    avg_price = Column(DECIMAL(20, 8))
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    
    __table_args__ = (
        UniqueConstraint('symbol', 'minute_time', name='uq_trade_agg'),
        Index('idx_trades_agg_symbol_time', 'symbol', 'minute_time'),
    )


class OrderbookSnapshot(Base):
    """Order book snapshots"""
    __tablename__ = 'orderbook_snapshots'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(TIMESTAMP, nullable=False)
    bid_total_volume = Column(DECIMAL(20, 8))
    ask_total_volume = Column(DECIMAL(20, 8))
    bid_ask_ratio = Column(DECIMAL(10, 4))
    spread = Column(DECIMAL(20, 8))
    spread_percent = Column(DECIMAL(10, 4))
    top_bid_price = Column(DECIMAL(20, 8))
    top_ask_price = Column(DECIMAL(20, 8))
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    
    __table_args__ = (
        Index('idx_orderbook_symbol_time', 'symbol', 'timestamp'),
    )


class FactorValue(Base):
    """Calculated factor values"""
    __tablename__ = 'factor_values'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(TIMESTAMP, nullable=False)
    
    # Price factors
    price_velocity_1m = Column(DECIMAL(10, 4))
    price_velocity_5m = Column(DECIMAL(10, 4))
    price_velocity_15m = Column(DECIMAL(10, 4))
    price_acceleration = Column(DECIMAL(10, 4))
    price_volatility = Column(DECIMAL(10, 4))
    
    # Volume factors
    volume_ratio_1m = Column(DECIMAL(10, 4))
    volume_ratio_5m = Column(DECIMAL(10, 4))
    volume_spike_score = Column(DECIMAL(10, 4))
    buy_sell_ratio = Column(DECIMAL(10, 4))
    large_trade_ratio = Column(DECIMAL(10, 4))
    
    # Liquidity factors
    liquidity_score = Column(DECIMAL(10, 4))
    bid_ask_imbalance = Column(DECIMAL(10, 4))
    spread_percent = Column(DECIMAL(10, 4))
    orderbook_pressure = Column(DECIMAL(10, 4))
    
    # Market factors
    market_cap_usd = Column(DECIMAL(20, 2))
    trade_intensity = Column(DECIMAL(10, 4))
    price_continuity = Column(DECIMAL(10, 4))
    rsi = Column(DECIMAL(10, 4))
    
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    
    __table_args__ = (
        UniqueConstraint('symbol', 'timestamp', name='uq_factors'),
        Index('idx_factors_symbol_time', 'symbol', 'timestamp'),
    )


class DetectionEvent(Base):
    """Detection events (PUMP/DUMP)"""
    __tablename__ = 'detection_events'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    event_type = Column(String(20), nullable=False)  # PUMP, DUMP, POTENTIAL_PUMP
    confidence_score = Column(DECIMAL(5, 4), nullable=False)
    trigger_factors = Column(JSONB)
    start_time = Column(TIMESTAMP)
    detection_time = Column(TIMESTAMP, nullable=False, index=True)
    start_price = Column(DECIMAL(20, 8))
    current_price = Column(DECIMAL(20, 8))
    peak_price = Column(DECIMAL(20, 8))
    max_change_percent = Column(DECIMAL(10, 4))
    status = Column(String(20), default='ACTIVE', index=True)
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    
    __table_args__ = (
        Index('idx_detection_symbol_time', 'symbol', 'detection_time'),
    )


# ==================== Database Connection Managers ====================

class PostgresManager:
    """PostgreSQL connection manager"""
    
    def __init__(self):
        self.engine = None
        self.Session = None
        self._connect()
    
    def _connect(self):
        """Establish database connection"""
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = os.getenv('POSTGRES_PORT', '5432')
        db = os.getenv('POSTGRES_DB', 'crypto_pump_dump')
        user = os.getenv('POSTGRES_USER', 'postgres')
        password = os.getenv('POSTGRES_PASSWORD', '')
        
        connection_string = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        
        try:
            self.engine = create_engine(
                connection_string,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_pre_ping=True,
                echo=False
            )
            self.Session = sessionmaker(bind=self.engine)
            logger.info(f"? Connected to PostgreSQL: {host}:{port}/{db}")
        except Exception as e:
            logger.error(f"? Failed to connect to PostgreSQL: {e}")
            raise
    
    def create_tables(self):
        """Create all tables"""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("? Database tables created successfully")
        except Exception as e:
            logger.error(f"? Failed to create tables: {e}")
            raise
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_session(self):
        """Get a new session"""
        return self.Session()
    
    def close(self):
        """Close all connections"""
        if self.engine:
            self.engine.dispose()
            logger.info("PostgreSQL connection closed")


class RedisManager:
    """Redis connection manager"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self._connect()
    
    def _connect(self):
        """Establish Redis connection"""
        host = os.getenv('REDIS_HOST', 'localhost')
        port = int(os.getenv('REDIS_PORT', 6379))
        password = os.getenv('REDIS_PASSWORD', None)
        db = int(os.getenv('REDIS_DB', 0))
        
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                password=password,
                db=db,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                max_connections=50
            )
            # Test connection
            self.client.ping()
            logger.info(f"? Connected to Redis: {host}:{port}")
        except Exception as e:
            logger.error(f"? Failed to connect to Redis: {e}")
            raise
    
    def set_price(self, symbol: str, price: float, timestamp: int):
        """Cache current price"""
        key = f"price:{symbol}"
        value = {"price": price, "timestamp": timestamp}
        self.client.setex(key, 60, str(value))
    
    def get_price(self, symbol: str) -> Optional[dict]:
        """Get cached price"""
        key = f"price:{symbol}"
        value = self.client.get(key)
        if value:
            return eval(value)
        return None
    
    def push_kline(self, symbol: str, interval: str, kline: dict):
        """Add kline to cache (keep last 60)"""
        key = f"klines:{symbol}:{interval}"
        self.client.lpush(key, str(kline))
        self.client.ltrim(key, 0, 59)
        self.client.expire(key, 3600)
    
    def get_klines(self, symbol: str, interval: str, limit: int = 60) -> list:
        """Get recent klines"""
        key = f"klines:{symbol}:{interval}"
        klines = self.client.lrange(key, 0, limit - 1)
        return [eval(k) for k in klines]
    
    def add_volume_window(self, symbol: str, timestamp: int, volume: float):
        """Add to volume sliding window"""
        key = f"volume_window:{symbol}"
        self.client.zadd(key, {str(volume): timestamp})
        # Remove old data (keep last hour)
        cutoff = timestamp - 3600
        self.client.zremrangebyscore(key, 0, cutoff)
        self.client.expire(key, 3600)
    
    def get_volume_window(self, symbol: str, start_time: int, end_time: int) -> list:
        """Get volumes in time window"""
        key = f"volume_window:{symbol}"
        volumes = self.client.zrangebyscore(key, start_time, end_time)
        return [float(v) for v in volumes]
    
    def set_orderbook(self, symbol: str, orderbook: dict):
        """Cache order book snapshot"""
        key = f"orderbook:{symbol}"
        self.client.hset(key, mapping=orderbook)
        self.client.expire(key, 10)
    
    def get_orderbook(self, symbol: str) -> Optional[dict]:
        """Get cached order book"""
        key = f"orderbook:{symbol}"
        return self.client.hgetall(key)
    
    def set_factors(self, symbol: str, factors: dict):
        """Cache calculated factors"""
        key = f"factors:{symbol}"
        self.client.hset(key, mapping=factors)
        self.client.expire(key, 60)
    
    def get_factors(self, symbol: str) -> Optional[dict]:
        """Get cached factors"""
        key = f"factors:{symbol}"
        factors = self.client.hgetall(key)
        if factors:
            # Convert string values back to float
            return {k: float(v) for k, v in factors.items()}
        return None
    
    def set_detection_status(self, symbol: str, status: dict):
        """Cache detection status"""
        key = f"detection:{symbol}:status"
        self.client.setex(key, 300, str(status))
    
    def get_detection_status(self, symbol: str) -> Optional[dict]:
        """Get detection status"""
        key = f"detection:{symbol}:status"
        value = self.client.get(key)
        if value:
            return eval(value)
        return None
    
    def update_watchlist(self, symbol: str, priority: float):
        """Update watchlist with priority"""
        self.client.zadd("watchlist", {symbol: priority})
    
    def get_watchlist(self, limit: int = 100) -> list:
        """Get top priority symbols"""
        return self.client.zrevrange("watchlist", 0, limit - 1)
    
    def close(self):
        """Close Redis connection"""
        if self.client:
            self.client.close()
            logger.info("Redis connection closed")


# ==================== Singleton Instances ====================

# Global database managers (initialized on first import)
postgres_manager = None
redis_manager = None


def init_databases():
    """Initialize database connections"""
    global postgres_manager, redis_manager
    
    if postgres_manager is None:
        postgres_manager = PostgresManager()
        postgres_manager.create_tables()
    
    if redis_manager is None:
        redis_manager = RedisManager()
    
    return postgres_manager, redis_manager


def get_postgres() -> PostgresManager:
    """Get PostgreSQL manager instance"""
    global postgres_manager
    if postgres_manager is None:
        postgres_manager = PostgresManager()
    return postgres_manager


def get_redis() -> RedisManager:
    """Get Redis manager instance"""
    global redis_manager
    if redis_manager is None:
        redis_manager = RedisManager()
    return redis_manager


if __name__ == "__main__":
    # Test database connections
    logger.add("logs/database.log", rotation="100 MB")
    
    print("Testing database connections...")
    pg, rd = init_databases()
    
    print("\n? Database setup completed!")
    print(f"PostgreSQL: {pg.engine.url}")
    print(f"Redis: Connected")
