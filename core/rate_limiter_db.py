"""
Async PostgreSQL Tabanlı Rate Limiter
Deque yapısından veritabanına dönüşüm
"""
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import RateLimitEntryDB
from datetime import datetime, timedelta


class RateLimiterDB:
    """Distributed rate limiter - PostgreSQL tabanlı"""
    
    def __init__(
        self, 
        session: AsyncSession,
        max_requests: int = 10,
        time_window: int = 60
    ):
        """
        Args:
            session: FastAPI Depends ile inject edilen AsyncSession
            max_requests: Zaman penceresi içinde izin verilen maksimum istek
            time_window: Zaman penceresi (saniye)
        """
        self.session = session
        self.max_requests = max_requests
        self.time_window = time_window
    
    async def is_allowed(self, client_ip: str, endpoint: str = None) -> bool:
        """
        İsteğin izin verilip verilmeyeceğini kontrol et
        
        Eski (deque):
            request_times = self.requests[client_ip]
            while request_times and request_times[0] < cutoff:
                request_times.popleft()
            return len(request_times) < self.max_requests
        
        Yeni (PostgreSQL):
            1. DELETE eski kayıtlar
            2. SELECT COUNT(*) son kayıtlar
            3. INSERT yeni kayıt (limit altındaysa)
        """
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(seconds=self.time_window)
        
        # 1. Eski kayıtları temizle
        await self._cleanup_old_entries(cutoff_time)
        
        # 2. Bu IP için mevcut istek sayısını kontrol et
        stmt = select(func.count()).select_from(RateLimitEntryDB).where(
            RateLimitEntryDB.client_ip == client_ip,
            RateLimitEntryDB.request_timestamp >= cutoff_time
        )
        result = await self.session.execute(stmt)
        current_count = result.scalar() or 0
        
        # 3. Limit kontrolü
        if current_count >= self.max_requests:
            return False
        
        # 4. Yeni istek kaydı ekle
        new_entry = RateLimitEntryDB(
            client_ip=client_ip,
            request_timestamp=current_time,
            endpoint=endpoint
        )
        self.session.add(new_entry)
        await self.session.flush()
        
        return True
    
    async def _cleanup_old_entries(self, cutoff_time: datetime):
        """Süresi dolmuş kayıtları temizle"""
        stmt = delete(RateLimitEntryDB).where(
            RateLimitEntryDB.request_timestamp < cutoff_time
        )
        await self.session.execute(stmt)
    
    async def get_remaining_requests(self, client_ip: str) -> int:
        """Kalan istek hakkını döndür"""
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(seconds=self.time_window)
        
        stmt = select(func.count()).select_from(RateLimitEntryDB).where(
            RateLimitEntryDB.client_ip == client_ip,
            RateLimitEntryDB.request_timestamp >= cutoff_time
        )
        result = await self.session.execute(stmt)
        current_count = result.scalar() or 0
        
        return max(0, self.max_requests - current_count)
