"""
Analyzer Configuration

Merkezi yapılandırma yönetimi.
Environment variable'lardan ayarları yükler.
"""
from dataclasses import dataclass, field
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AnalyzerConfig:
    """
    Gemini Analyzer yapılandırma container'ı
    
    Tüm ayarlar merkezi olarak burada yönetilir.
    Environment variable'lardan okunur, varsayılanlar sağlanır.
    """
    
    # API Ayarları
    api_key: str = ""
    model_name: str = "gemini-2.5-flash-lite"
    temperature: float = 0.3
    max_tokens: int = 1024
    
    # Retry Ayarları
    max_retries: int = 4
    retry_min_wait: int = 1
    retry_max_wait: int = 10
    
    # Rate Limit Ayarları
    rate_limit_max: int = 10
    rate_limit_window: int = 60  # saniye
    
    # Cache Ayarları
    cache_ttl: int = 300  # 5 dakika
    
    @classmethod
    def from_env(cls) -> "AnalyzerConfig":
        """
        Environment variable'lardan yapılandırma yükle
        
        Returns:
            AnalyzerConfig: Yapılandırılmış instance
        """
        api_key = os.getenv("GEMINI_API_KEY", "")
        
        # API key kontrolü
        if api_key == "your_api_key_here":
            api_key = ""
        
        return cls(
            # API
            api_key=api_key,
            model_name=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
            temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("GEMINI_MAX_TOKENS", "1024")),
            
            # Retry
            max_retries=int(os.getenv("GEMINI_MAX_RETRIES", "4")),
            retry_min_wait=int(os.getenv("GEMINI_RETRY_MIN_WAIT", "1")),
            retry_max_wait=int(os.getenv("GEMINI_RETRY_MAX_WAIT", "10")),
            
            # Rate Limit
            rate_limit_max=int(os.getenv("GEMINI_RATE_LIMIT", "10")),
            rate_limit_window=int(os.getenv("GEMINI_RATE_LIMIT_WINDOW", "60")),
            
            # Cache
            cache_ttl=int(os.getenv("GEMINI_CACHE_TTL", "300")),
        )
    
    @property
    def is_configured(self) -> bool:
        """API key'in geçerli olup olmadığını kontrol et"""
        return bool(self.api_key) and self.api_key != "your_api_key_here"
    
    def __str__(self) -> str:
        """Debug için string representation"""
        return (
            f"AnalyzerConfig("
            f"model={self.model_name}, "
            f"rate_limit={self.rate_limit_max}/min, "
            f"cache_ttl={self.cache_ttl}s, "
            f"configured={self.is_configured})"
        )
