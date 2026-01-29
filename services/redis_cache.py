"""
Redis Cache Servisi

Pydantic modelleri için Redis cache servisi.
String/JSON stratejisi ile otomatik serileştirme/deserileştirme.

Özellikler:
- Otomatik JSON serileştirme (model_dump_json)
- Otomatik Pydantic validasyonu (model_validate_json)
- Deterministik cache key üretimi (SHA256)
- TTL (Time To Live) yönetimi
- SCAN tabanlı toplu silme (KEYS kullanmıyor)
"""
import redis.asyncio as redis
import json
import hashlib
from typing import Optional, TypeVar, Type
from pydantic import BaseModel

# Generic type for Pydantic models
T = TypeVar('T', bound=BaseModel)


class RedisCacheService:
    """
    Pydantic modelleri için Redis cache servisi
    
    Cache-Aside Pattern:
    1. İstek geldi
    2. Cache'te var mı? → EVET → Döndür (HIT)
                       → HAYIR → API'ye git → Cache'e yaz → Döndür (MISS)
    
    Veri Saklama:
    - Redis STRING yapısı kullanılır (HASH değil)
    - JSON formatında serileştirme
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        key_prefix: str = "cache",
        default_ttl: int = 300  # 5 dakika
    ):
        """
        Args:
            redis_client: Redis bağlantısı (RedisManager.get_client())
            key_prefix: Cache key prefix'i
            default_ttl: Varsayılan TTL (saniye)
        """
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
    
    def _get_key(self, identifier: str) -> str:
        """
        Tam cache key oluştur
        
        Args:
            identifier: Cache tanımlayıcısı (hash veya özel string)
        
        Returns:
            str: Tam Redis key (örn: "cache:abc123def456")
        """
        return f"{self.key_prefix}:{identifier}"
    
    @staticmethod
    def generate_hash_key(*args, **kwargs) -> str:
        """
        Deterministic cache key oluştur (SHA256)
        
        Aynı parametreler her zaman aynı key'i üretir.
        JSON serileştirme ile güvenli dönüşüm sağlanır.
        
        Args:
            *args: Pozisyon argümanları
            **kwargs: İsimli argümanları
        
        Returns:
            str: 16 karakterlik SHA256 hash (örn: "a1b2c3d4e5f67890")
        
        Example:
            >>> RedisCacheService.generate_hash_key(total=100, confidence=0.78)
            'f7a8b9c0d1e2f3a4'
        """
        # Argümanları birleştir
        cache_data = {
            "args": args,
            "kwargs": kwargs
        }
        
        # JSON string oluştur (sıralı, deterministic)
        # default=str: datetime gibi non-serializable tipleri string'e çevirir
        json_str = json.dumps(cache_data, sort_keys=True, default=str)
        
        # SHA256 hash oluştur (ilk 16 karakter)
        hash_obj = hashlib.sha256(json_str.encode())
        return hash_obj.hexdigest()[:16]
    
    async def get(
        self,
        key: str,
        model_class: Type[T]
    ) -> Optional[T]:
        """
        Cache'ten Pydantic model oku
        
        Args:
            key: Cache key (veya identifier)
            model_class: Dönüştürülecek Pydantic model sınıfı
        
        Returns:
            Pydantic model instance veya None (cache miss)
        
        Example:
            >>> report = await cache.get("abc123", GeminiAnalysisReport)
            >>> if report:
            ...     print("Cache HIT!")
        """
        full_key = self._get_key(key)
        
        try:
            # Redis'ten string oku
            data = await self.redis.get(full_key)
            
            if data is None:
                return None  # Cache MISS
            
            # JSON string → Pydantic model
            return model_class.model_validate_json(data)
            
        except Exception as e:
            print(f"⚠️ Cache okuma hatası: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: BaseModel,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Pydantic model'i cache'e yaz
        
        Args:
            key: Cache key (veya identifier)
            value: Kaydedilecek Pydantic model
            ttl: TTL (saniye), None ise default kullanılır
        
        Returns:
            bool: Başarılı ise True
        
        Example:
            >>> success = await cache.set("abc123", report, ttl=300)
        """
        full_key = self._get_key(key)
        ttl = ttl or self.default_ttl
        
        try:
            # Pydantic model → JSON string
            json_data = value.model_dump_json()
            
            # Redis'e kaydet (TTL ile)
            await self.redis.setex(full_key, ttl, json_data)
            return True
            
        except Exception as e:
            print(f"⚠️ Cache yazma hatası: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Cache key'ini sil
        
        Args:
            key: Silinecek cache key
        
        Returns:
            bool: Silme başarılı ise True
        """
        full_key = self._get_key(key)
        result = await self.redis.delete(full_key)
        return result > 0
    
    async def exists(self, key: str) -> bool:
        """
        Cache key'i var mı kontrol et
        
        Args:
            key: Kontrol edilecek key
        
        Returns:
            bool: Key varsa True
        """
        full_key = self._get_key(key)
        result = await self.redis.exists(full_key)
        return result > 0
    
    async def get_ttl(self, key: str) -> int:
        """
        Kalan TTL'i döndür (saniye)
        
        Args:
            key: TTL sorgulanacak key
        
        Returns:
            int: Kalan saniye, -2 = key yok, -1 = TTL yok
        """
        full_key = self._get_key(key)
        return await self.redis.ttl(full_key)
    
    async def clear_prefix(self, pattern: str = "*") -> int:
        """
        Belirli pattern'e uyan tüm cache'leri temizle
        
        ⚠️ Production'da dikkatli kullanın!
        
        NOT: KEYS komutu yerine SCAN kullanılır (performans için)
        KEYS tüm key'leri tek seferde döndürür → Redis bloklanır
        SCAN iteratif çalışır → Redis bloklanmaz
        
        Args:
            pattern: Glob pattern (örn: "*", "gemini_*")
        
        Returns:
            int: Silinen key sayısı
        """
        full_pattern = f"{self.key_prefix}:{pattern}"
        cursor = 0
        deleted = 0
        
        # SCAN ile iteratif key bulma
        while True:
            cursor, keys = await self.redis.scan(
                cursor=cursor, 
                match=full_pattern, 
                count=100  # Her iterasyonda max 100 key
            )
            
            if keys:
                # Bulunan key'leri sil
                deleted += await self.redis.delete(*keys)
            
            # Cursor 0 olduğunda tüm key'ler tarandı
            if cursor == 0:
                break
        
        return deleted
    
    async def get_or_set(
        self,
        key: str,
        model_class: Type[T],
        factory,  # Callable that returns T
        ttl: Optional[int] = None
    ) -> T:
        """
        Cache'te varsa döndür, yoksa factory'den al ve kaydet
        
        Bu method Cache-Aside pattern'i tek çağrıda uygular.
        
        Args:
            key: Cache key
            model_class: Pydantic model sınıfı
            factory: Cache miss durumunda çağrılacak async fonksiyon
            ttl: TTL (saniye)
        
        Returns:
            T: Cache'teki veya factory'den gelen model
        
        Example:
            >>> async def fetch_from_api():
            ...     return await gemini.analyze(...)
            >>> 
            >>> report = await cache.get_or_set(
            ...     key="abc123",
            ...     model_class=GeminiAnalysisReport,
            ...     factory=fetch_from_api,
            ...     ttl=300
            ... )
        """
        # Cache kontrolü
        cached = await self.get(key, model_class)
        if cached is not None:
            return cached
        
        # Cache miss - factory'den al
        value = await factory()
        
        # Cache'e kaydet
        await self.set(key, value, ttl)
        
        return value
    
    async def get_or_set_with_lock(
        self,
        key: str,
        model_class: Type[T],
        factory,  # Callable that returns Awaitable[T]
        ttl: Optional[int] = None,
        lock_timeout: int = 30,
        lock_blocking_timeout: float = 10.0
    ) -> T:
        """
        Cache Stampede korumalı get-or-set operasyonu
        
        Double-Checked Locking Pattern:
        1. Cache kontrolü (hızlı path)
        2. Lock edin
        3. TEKRAR cache kontrolü (biri yazmış olabilir)
        4. Factory çalıştır (API çağrısı)
        5. Cache'e yaz
        
        ╔═══════════════════════════════════════════════════════════════════╗
        ║ CACHE STAMPEDE NEDİR?                                              ║
        ╠═══════════════════════════════════════════════════════════════════╣
        ║ 50 istek aynı anda geliyor, hepsi cache miss alıyor               ║
        ║ → 50 paralel API çağrısı → Maliyet + Rate Limit aşımı!            ║
        ║                                                                    ║
        ║ ÇÖZÜM: Lock ile sadece 1 istek API'ye gider, diğerleri bekler     ║
        ╚═══════════════════════════════════════════════════════════════════╝
        
        Args:
            key: Cache key
            model_class: Pydantic model sınıfı (deserialize için)
            factory: Cache miss durumunda çalıştırılacak async fonksiyon
            ttl: Cache TTL (saniye)
            lock_timeout: Lock'un maksimum tutulma süresi (saniye)
            lock_blocking_timeout: Lock bekleme timeout'u (saniye)
            
        Returns:
            T: Cache'teki veya factory'den gelen değer
            
        Raises:
            LockError: Lock alınamazsa
            Exception: Factory hatası
        """
        full_key = self._get_key(key)
        lock_key = f"{full_key}:lock"
        ttl = ttl or self.default_ttl
        
        # ═══════════════════════════════════════════════════════════════
        # ADIM 1: İLK CACHE KONTROLÜ (Fast Path)
        # Lock almadan önce kontrol et - çoğu durumda cache hit olacak
        # ═══════════════════════════════════════════════════════════════
        cached = await self.get(key, model_class)
        if cached is not None:
            print(f"📦 Cache HIT (no lock needed): {key[:8]}...")
            return cached
        
        print(f"📭 Cache MISS (acquiring lock): {key[:8]}...")
        
        # ═══════════════════════════════════════════════════════════════
        # ADIM 2: LOCK EDİN
        # Sadece 1 istek API'ye gidebilir, diğerleri bekler
        # ═══════════════════════════════════════════════════════════════
        lock = self.redis.lock(
            lock_key,
            timeout=lock_timeout,
            blocking_timeout=lock_blocking_timeout
        )
        
        try:
            acquired = await lock.acquire(blocking=True)
            
            if not acquired:
                # Lock alınamadı (timeout) - factory'yi direkt çalıştır
                print(f"⚠️ Lock timeout, factory çalıştırılıyor: {key[:8]}...")
                return await factory()
            
            print(f"🔒 Lock acquired: {key[:8]}...")
            
            # ═══════════════════════════════════════════════════════════
            # ADIM 3: DOUBLE-CHECK (Biz beklerken biri yazmış olabilir)
            # ═══════════════════════════════════════════════════════════
            cached = await self.get(key, model_class)
            if cached is not None:
                print(f"📦 Cache HIT (after lock): {key[:8]}...")
                return cached
            
            # ═══════════════════════════════════════════════════════════
            # ADIM 4: FACTORY ÇALIŞTIR (API çağrısı)
            # ═══════════════════════════════════════════════════════════
            print(f"🏭 Factory çalıştırılıyor: {key[:8]}...")
            result = await factory()
            
            # ═══════════════════════════════════════════════════════════
            # ADIM 5: CACHE'E YAZ
            # ═══════════════════════════════════════════════════════════
            await self.set(key, result, ttl=ttl)
            print(f"💾 Cache yazıldı: {key[:8]}... (TTL: {ttl}s)")
            
            return result
            
        finally:
            # ═══════════════════════════════════════════════════════════
            # ADIM 6: LOCK SERBEST BIRAK
            # ═══════════════════════════════════════════════════════════
            try:
                await lock.release()
                print(f"🔓 Lock released: {key[:8]}...")
            except Exception:
                pass  # Lock zaten serbest veya timeout olmuş olabilir
    
    async def get_stats(self) -> dict:
        """
        Cache istatistikleri (debug için)
        
        Returns:
            dict: İstatistik bilgileri
        """
        pattern = f"{self.key_prefix}:*"
        cursor = 0
        key_count = 0
        
        # Key sayısını hesapla (SCAN ile)
        while True:
            cursor, keys = await self.redis.scan(cursor=cursor, match=pattern, count=100)
            key_count += len(keys)
            if cursor == 0:
                break
        
        return {
            "prefix": self.key_prefix,
            "cached_items": key_count,
            "default_ttl": self.default_ttl
        }
