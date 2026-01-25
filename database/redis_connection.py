"""
Async Redis Bağlantı Yönetimi
Singleton Pattern + Connection Pooling
"""
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


class RedisManager:
    """
    Redis bağlantı havuzu yöneticisi
    
    Singleton pattern: Tüm uygulama tek bir pool kullanır
    Connection pooling: Her request için yeni bağlantı açmak yerine havuzdan al
    """
    
    _pool: Optional[ConnectionPool] = None
    _client: Optional[redis.Redis] = None
    
    @classmethod
    async def initialize(cls) -> None:
        """
        Uygulama başlangıcında çağrılır (startup event)
        
        Connection pool oluşturur ve bağlantıyı test eder.
        """
        if cls._pool is not None:
            return  # Zaten başlatılmış
        
        redis_url = os.getenv(
            "REDIS_URL", 
            "redis://localhost:6379/0"
        )
        
        # Connection Pool oluştur
        cls._pool = ConnectionPool.from_url(
            redis_url,
            max_connections=20,        # Maksimum bağlantı sayısı
            decode_responses=True,     # bytes yerine str döndür
            socket_timeout=5.0,        # Bağlantı timeout (saniye)
            socket_connect_timeout=5.0,
        )
        
        # Client oluştur
        cls._client = redis.Redis(connection_pool=cls._pool)
        
        # Bağlantı testi
        try:
            await cls._client.ping()
            print("✅ Redis bağlantısı başarılı")
        except redis.ConnectionError as e:
            print(f"❌ Redis bağlantı hatası: {e}")
            cls._pool = None
            cls._client = None
    
    @classmethod
    async def close(cls) -> None:
        """
        Uygulama kapanışında çağrılır (shutdown event)
        
        Tüm bağlantıları temiz bir şekilde kapatır.
        """
        if cls._client:
            await cls._client.close()
        if cls._pool:
            await cls._pool.disconnect()
        
        cls._client = None
        cls._pool = None
        print("🔴 Redis bağlantısı kapatıldı")
    
    @classmethod
    def get_client(cls) -> redis.Redis:
        """
        Redis client instance'ını döndür
        
        Returns:
            redis.Redis: Aktif Redis client
            
        Raises:
            RuntimeError: Redis başlatılmamışsa
        """
        if cls._client is None:
            raise RuntimeError(
                "Redis başlatılmamış! "
                "RedisManager.initialize() çağrıldığından emin olun."
            )
        return cls._client
    
    @classmethod
    async def health_check(cls) -> dict:
        """
        Health check endpoint'i için durum bilgisi
        
        Returns:
            dict: Redis sağlık durumu ve memory bilgisi
        """
        if cls._client is None:
            return {
                "status": "disconnected",
                "error": "Redis client not initialized"
            }
        
        try:
            # PING testi
            await cls._client.ping()
            
            # Memory bilgisi al
            info = await cls._client.info("memory")
            
            return {
                "status": "healthy",
                "used_memory": info.get("used_memory_human", "unknown"),
                "max_memory": info.get("maxmemory_human", "256mb"),
                "connected_clients": (await cls._client.info("clients")).get("connected_clients", 0),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# ═══════════════════════════════════════════════════════════════════
# DEPENDENCY FUNCTION
# ═══════════════════════════════════════════════════════════════════

async def get_redis() -> redis.Redis:
    """
    FastAPI Depends için kısayol fonksiyonu
    
    Usage:
        @router.get("/example")
        async def example(redis: redis.Redis = Depends(get_redis)):
            await redis.get("key")
    """
    return RedisManager.get_client()
