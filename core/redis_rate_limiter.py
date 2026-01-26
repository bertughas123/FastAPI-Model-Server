"""
Redis Tabanlı Sliding Window Rate Limiter

Algoritma:
1. Eski kayıtları temizle (window dışındakiler)
2. Mevcut istek sayısını say
3. Limit altındaysa yeni kaydı ekle
4. Tüm işlemleri atomic pipeline ile yap (race condition önle)

Veri Yapısı (ZSET):
- Key: "prefix:identifier" (Örn: ratelimit:global)
- Score: Unix Timestamp (milisaniye)
- Member: "timestamp:uuid" (benzersiz)
"""
import redis.asyncio as redis
import time
import uuid
from typing import Tuple


class RedisRateLimiter:
    """
    Sliding Window Rate Limiter (Redis ZSET)
    
    Global veya per-identifier rate limiting için kullanılabilir.
    Tüm worker'lar aynı Redis sayacını paylaşır (distributed).
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        key_prefix: str = "ratelimit",
        max_requests: int = 10,
        window_seconds: int = 60
    ):
        """
        Args:
            redis_client: Redis bağlantısı (RedisManager.get_client())
            key_prefix: Redis key prefix'i
            max_requests: Pencere içinde izin verilen maksimum istek
            window_seconds: Pencere süresi (saniye)
        """
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.window_ms = window_seconds * 1000  # Milisaniye cinsinden
    
    def _get_key(self, identifier: str = "global") -> str:
        """
        Rate limit key'i oluştur
        
        Args:
            identifier: Takip edilecek tanımlayıcı
                       - "global" → Tüm sistem için tek limit
                       - IP adresi → Kullanıcı bazlı limit
        
        Returns:
            str: Redis key (örn: "ratelimit:global")
        """
        return f"{self.key_prefix}:{identifier}"
    
    async def is_allowed(self, identifier: str = "global") -> Tuple[bool, int]:
        """
        İsteğin izin verilip verilmeyeceğini kontrol et
        
        Sliding Window Algoritması (Tamamen Atomic):
        1. ZREMRANGEBYSCORE: Süresi dolan kayıtları sil
        2. ZCARD: Mevcut istek sayısını al
        3. Limit kontrolü yap
        4. ZADD: Limit altındaysa yeni kaydı ekle (aynı pipeline'da)
        5. EXPIRE: Key'e TTL ekle
        
        Race Condition Önleme:
        - Tüm işlemler tek bir pipeline'da atomic olarak yapılır
        - Önce ekleme yapılır, sonra limit kontrolü edilir
        - Limit aşılırsa eklenen kayıt silinir (rollback)
        
        Args:
            identifier: Takip edilecek tanımlayıcı
        
        Returns:
            Tuple[bool, int]: (izin_var_mı, kalan_hak)
        """
        key = self._get_key(identifier)
        now_ms = int(time.time() * 1000)
        window_start_ms = now_ms - self.window_ms
        
        # Benzersiz request ID oluştur
        request_id = f"{now_ms}:{uuid.uuid4().hex[:8]}"
        
        try:
            # Atomic pipeline - tüm işlemler tek seferde
            async with self.redis.pipeline(transaction=True) as pipe:
                # 1. Süresi dolan kayıtları sil
                pipe.zremrangebyscore(key, "-inf", window_start_ms)
                
                # 2. Yeni kaydı ÖNCE ekle (atomic olması için)
                pipe.zadd(key, {request_id: now_ms})
                
                # 3. Toplam sayıyı al (ekleme sonrası)
                pipe.zcard(key)
                
                # 4. TTL güncelle
                pipe.expire(key, self.window_seconds + 10)
                
                # Pipeline'ı çalıştır
                results = await pipe.execute()
                # results[0] = zremrangebyscore sonucu
                # results[1] = zadd sonucu
                # results[2] = zcard sonucu (yeni kayıt DAHİL)
                # results[3] = expire sonucu
                
                current_count = results[2]
            
            # 5. Limit kontrolü (eşik aşıldıysa rollback)
            if current_count > self.max_requests:
                # Limit aşıldı - eklenen kaydı sil (rollback)
                await self.redis.zrem(key, request_id)
                remaining = 0
                return False, remaining
            
            # Başarılı - kalan hakkı hesapla
            remaining = self.max_requests - current_count
            return True, remaining
            
        except redis.RedisError as e:
            print(f"⚠️ Redis hatası: {e}")
            # Redis hatası durumunda izin ver (fail-open)
            return True, self.max_requests
    
    async def get_remaining(self, identifier: str = "global") -> int:
        """
        Kalan istek hakkını döndür (değişiklik yapmadan)
        
        Args:
            identifier: Takip edilecek tanımlayıcı
        
        Returns:
            int: Kalan istek hakkı
        """
        key = self._get_key(identifier)
        now_ms = int(time.time() * 1000)
        window_start_ms = now_ms - self.window_ms
        
        # Pencere içindeki istek sayısı (ZCOUNT)
        count = await self.redis.zcount(key, window_start_ms, "+inf")
        return max(0, self.max_requests - count)
    
    async def get_reset_time(self, identifier: str = "global") -> int:
        """
        Limitin ne zaman sıfırlanacağını döndür (saniye)
        
        En eski kaydın expire olacağı zamanı hesaplar.
        Formula: (En Eski Timestamp + Window Süresi) - Şu Anki Zaman
        
        Args:
            identifier: Takip edilecek tanımlayıcı
        
        Returns:
            int: Sıfırlanmaya kalan saniye (0 = limit açık)
        """
        key = self._get_key(identifier)
        
        # En eski kaydı al (0. index)
        oldest = await self.redis.zrange(key, 0, 0, withscores=True)
        
        if not oldest:
            return 0  # Kayıt yok, limit açık
        
        # oldest = [(member, score), ...]
        oldest_timestamp_ms = oldest[0][1]
        now_ms = int(time.time() * 1000)
        
        # Expire zamanı = En eski timestamp + Window süresi
        expires_at_ms = oldest_timestamp_ms + self.window_ms
        
        remaining_ms = expires_at_ms - now_ms
        return max(0, int(remaining_ms / 1000))
    
    async def reset(self, identifier: str = "global") -> bool:
        """
        Rate limit sayacını sıfırla (test için)
        
        Args:
            identifier: Sıfırlanacak tanımlayıcı
        
        Returns:
            bool: Silme başarılı ise True
        """
        key = self._get_key(identifier)
        result = await self.redis.delete(key)
        return result > 0
    
    async def get_stats(self, identifier: str = "global") -> dict:
        """
        Rate limiter istatistikleri (debug için)
        
        Args:
            identifier: Takip edilecek tanımlayıcı
        
        Returns:
            dict: İstatistik bilgileri
        """
        key = self._get_key(identifier)
        now_ms = int(time.time() * 1000)
        window_start_ms = now_ms - self.window_ms
        
        # Mevcut sayı
        current_count = await self.redis.zcount(key, window_start_ms, "+inf")
        
        # TTL
        ttl = await self.redis.ttl(key)
        
        # Reset time
        reset_time = await self.get_reset_time(identifier)
        
        return {
            "key": key,
            "current_count": current_count,
            "max_requests": self.max_requests,
            "remaining": max(0, self.max_requests - current_count),
            "window_seconds": self.window_seconds,
            "ttl_seconds": ttl,
            "reset_in_seconds": reset_time
        }
