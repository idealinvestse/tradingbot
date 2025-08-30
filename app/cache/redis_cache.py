"""Redis cache layer for API responses and frequently accessed data."""

import pickle
from typing import Any

import redis
from pydantic import BaseModel

from app.strategies.utils import get_json_logger

logger = get_json_logger("redis_cache")


class CacheConfig(BaseModel):
    """Redis cache configuration."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    default_ttl: int = 300  # 5 minutes default
    max_connections: int = 50
    socket_timeout: int = 5


class RedisCache:
    """Redis caching implementation."""

    def __init__(self, config: CacheConfig = None):
        """Initialize Redis cache."""
        self.config = config or CacheConfig()
        self.client = None
        self._connect()

    def _connect(self):
        """Connect to Redis."""
        try:
            self.client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                max_connections=self.config.max_connections,
                socket_timeout=self.config.socket_timeout,
                decode_responses=False,
            )
            self.client.ping()
            logger.info("Redis connection established")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if not self.client:
            return None

        try:
            value = self.client.get(key)
            if value:
                return pickle.loads(value)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None

    def set(self, key: str, value: Any, ttl: int | None = None):
        """Set value in cache."""
        if not self.client:
            return False

        ttl = ttl or self.config.default_ttl
        try:
            serialized = pickle.dumps(value)
            self.client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
        return False

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.client:
            return False

        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
        return False

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.client:
            return False

        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
        return False

    def invalidate_pattern(self, pattern: str):
        """Invalidate keys matching pattern."""
        if not self.client:
            return

        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Cache invalidate error: {e}")


class CacheDecorator:
    """Decorator for caching function results."""

    def __init__(self, ttl: int = 300, key_prefix: str = ""):
        """Initialize cache decorator."""
        self.ttl = ttl
        self.key_prefix = key_prefix
        self.cache = RedisCache()

    def __call__(self, func):
        """Decorator implementation."""

        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{self.key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"

            # Check cache
            cached_value = self.cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            # Execute function
            result = func(*args, **kwargs)

            # Store in cache
            self.cache.set(cache_key, result, self.ttl)
            logger.debug(f"Cache miss: {cache_key}")

            return result

        return wrapper


class DataCache:
    """Specialized cache for market data."""

    def __init__(self):
        """Initialize data cache."""
        self.cache = RedisCache()

    def cache_ohlcv(self, exchange: str, symbol: str, timeframe: str, data: list, ttl: int = 60):
        """Cache OHLCV data."""
        key = f"ohlcv:{exchange}:{symbol}:{timeframe}"
        return self.cache.set(key, data, ttl)

    def get_ohlcv(self, exchange: str, symbol: str, timeframe: str) -> list | None:
        """Get cached OHLCV data."""
        key = f"ohlcv:{exchange}:{symbol}:{timeframe}"
        return self.cache.get(key)

    def cache_orderbook(self, exchange: str, symbol: str, data: dict, ttl: int = 5):
        """Cache orderbook data."""
        key = f"orderbook:{exchange}:{symbol}"
        return self.cache.set(key, data, ttl)

    def get_orderbook(self, exchange: str, symbol: str) -> dict | None:
        """Get cached orderbook."""
        key = f"orderbook:{exchange}:{symbol}"
        return self.cache.get(key)

    def cache_ticker(self, exchange: str, symbol: str, data: dict, ttl: int = 10):
        """Cache ticker data."""
        key = f"ticker:{exchange}:{symbol}"
        return self.cache.set(key, data, ttl)

    def get_ticker(self, exchange: str, symbol: str) -> dict | None:
        """Get cached ticker."""
        key = f"ticker:{exchange}:{symbol}"
        return self.cache.get(key)
