"""
Rate Limiting Sistemi
IP tabanlı istek sınırlandırma
"""
from typing import Dict
from collections import deque, defaultdict
import time


class RateLimiter:
    """IP tabanlı basit rate limiter"""
    
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        """
        Args:
            max_requests: Zaman penceresi içinde maksimum istek sayısı
            time_window: Zaman penceresi (saniye)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, deque] = defaultdict(deque)
    
    def is_allowed(self, client_ip: str) -> bool:
        """
        İsteğin izin verilip verilmeyeceğini kontrol et
        
        Args:
            client_ip: İstemci IP adresi
            
        Returns:
            True: İstek kabul edilebilir
            False: Rate limit aşıldı
        """
        current_time = time.time()
        request_times = self.requests[client_ip]
        
        # Eski timestamp'leri temizle
        while request_times and request_times[0] < current_time - self.time_window:
            request_times.popleft()
        
        # Limit kontrolü
        if len(request_times) >= self.max_requests:
            return False
        
        # Yeni timestamp ekle
        request_times.append(current_time)
        return True


# Global rate limiter instance
rate_limiter = RateLimiter(max_requests=10, time_window=60)
