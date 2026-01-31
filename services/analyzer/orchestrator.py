"""
Gemini Analyzer Orchestrator

Tüm bileşenleri koordine eden ana orkestratör.
Separation of Concerns: Sadece bileşen koordinasyonu yapar.
"""
from typing import Optional

from tenacity import RetryError
from google.api_core.exceptions import ResourceExhausted

from schemas.metrics import AggregatedMetrics, GeminiAnalysisReport
from database.redis_connection import RedisManager
from core.redis_rate_limiter import RedisRateLimiter
from services.redis_cache import RedisCacheService

# Analyzer bileşenleri
from services.analyzer.config import AnalyzerConfig
from services.analyzer.prompts import PromptBuilder
from services.analyzer.client import GeminiAPIClient
from services.analyzer.parser import ResponseParser, ParseError
from services.analyzer.fallback import FallbackEngine


class GeminiAnalyzerOrchestrator:
    """
    Gemini tabanlı performans analizi için ana orkestratör
    
    Koordine eder:
    - Cache araması (RedisCacheService)
    - Rate limiting (RedisRateLimiter)
    - Prompt oluşturma (PromptBuilder)
    - API iletişimi (GeminiAPIClient)
    - Yanıt ayrıştırma (ResponseParser)
    - Fallback yönetimi (FallbackEngine)
    
    Akış (get_or_set_with_lock):
    1. Cache kontrolü (HIT → direkt döndür)
    2. Lock edin (sadece 1 istek API'ye gider)
    3. Double-check cache (biri yazmış olabilir)
    4. Factory çalıştır (rate limit + API + parse)
    5. Cache'e kaydet
    6. Lock serbest bırak
    """
    
    # Class-level services (singleton pattern)
    _rate_limiter: Optional[RedisRateLimiter] = None
    _cache_service: Optional[RedisCacheService] = None
    
    def __init__(self, config: Optional[AnalyzerConfig] = None):
        """
        Orkestratörü başlat
        
        Args:
            config: Yapılandırma (None ise env'den yüklenir)
        """
        # Yapılandırma
        self.config = config or AnalyzerConfig.from_env()
        
        # Bileşenleri başlat
        self.prompt_builder = PromptBuilder()
        self.api_client = GeminiAPIClient(self.config)
        self.parser = ResponseParser()
        self.fallback = FallbackEngine()
        
        # Başlangıç mesajı
        if self.api_client.is_configured:
            print(f"✅ Gemini Analyzer Orchestrator hazır")
            print(f"   Rate Limit: {self.config.rate_limit_max} req/min (Global)")
            print(f"   Cache TTL: {self.config.cache_ttl}s")
    
    def _ensure_services(self) -> None:
        """
        Redis servislerinin başlatıldığından emin ol (Lazy Initialization)
        
        Neden lazy?
        - __init__ sırasında Redis bağlantısı olmayabilir
        - Servisleri sadece gerçekten ihtiyaç duyulduğunda başlat
        - Singleton pattern ile tekrar yaratmayı önle
        """
        if GeminiAnalyzerOrchestrator._rate_limiter is None:
            redis_client = RedisManager.get_client()
            
            # Global rate limiter (tüm worker'lar paylaşır)
            GeminiAnalyzerOrchestrator._rate_limiter = RedisRateLimiter(
                redis_client=redis_client,
                key_prefix="gemini_ratelimit",
                max_requests=self.config.rate_limit_max,
                window_seconds=self.config.rate_limit_window
            )
            
            # Cache servisi
            GeminiAnalyzerOrchestrator._cache_service = RedisCacheService(
                redis_client=redis_client,
                key_prefix="gemini_cache",
                default_ttl=self.config.cache_ttl
            )
            
            print("   🔄 Redis servisleri başlatıldı (lazy init)")
    
    def _generate_cache_key(
        self,
        current: AggregatedMetrics,
        previous: Optional[AggregatedMetrics]
    ) -> str:
        """
        Metrikler için deterministic cache key oluştur
        
        Aynı metrikler → Aynı key → Cache HIT
        
        Hassasiyet:
        - confidence: 2 ondalık
        - latency: 1 ondalık
        - time: dakika hassasiyeti
        """
        return RedisCacheService.generate_hash_key(
            total=current.total_predictions,
            confidence=round(current.average_confidence, 2),
            latency=round(current.average_inference_time_ms, 1),
            time=current.time_window_end.isoformat()[:16],
            prev_total=previous.total_predictions if previous else 0
        )
    
    async def _fetch_from_gemini(
        self,
        current_metrics: AggregatedMetrics,
        previous_metrics: Optional[AggregatedMetrics]
    ) -> GeminiAnalysisReport:
        """
        Gemini'den rapor al (Rate Limit + API + Parse)
        
        Bu factory fonksiyonu get_or_set_with_lock içinde çağrılır.
        Lock içinde çalışır, yani sadece 1 istek API'ye gider.
        
        Args:
            current_metrics: Güncel metrikler
            previous_metrics: Karşılaştırma için önceki metrikler
            
        Returns:
            GeminiAnalysisReport: Analiz raporu
            
        Raises:
            Exception: Rate limit aşıldıysa veya API hatası
        """
        # Rate limit kontrolü
        allowed, remaining = await GeminiAnalyzerOrchestrator._rate_limiter.is_allowed("global")
        
        if not allowed:
            reset_time = await GeminiAnalyzerOrchestrator._rate_limiter.get_reset_time("global")
            raise Exception(
                f"Global rate limit aşıldı ({self.config.rate_limit_max}/dk). "
                f"Yeniden deneme: {reset_time} saniye"
            )
        
        print(f"🚦 Rate limit OK. Kalan: {remaining}")
        
        # Prompt oluştur
        prompt = self.prompt_builder.build_analysis_prompt(current_metrics, previous_metrics)
        
        # API çağrısı (Retry korumalı)
        response_text = await self.api_client.generate(prompt)
        
        # Parse et (try_parse ile hata yönetimi)
        report, error = self.parser.try_parse(response_text, current_metrics)
        
        if error:
            raise ParseError(error)
        
        return report
    
    async def analyze_performance(
        self,
        current_metrics: AggregatedMetrics,
        previous_metrics: Optional[AggregatedMetrics] = None
    ) -> GeminiAnalysisReport:
        """
        Performans metriklerini Gemini ile analiz et
        (Cache Stampede korumalı - Distributed Locking)
        
        Args:
            current_metrics: Güncel metrikler
            previous_metrics: Karşılaştırma için önceki metrikler (opsiyonel)
            
        Returns:
            GeminiAnalysisReport: Analiz raporu
        """
        # API key kontrolü
        if not self.api_client.is_configured:
            return self.fallback.create_fallback_report(
                current_metrics,
                "Gemini API key yapılandırılmamış"
            )
        
        # Redis servislerini başlat (lazy)
        self._ensure_services()
        
        # Cache key oluştur
        cache_key = self._generate_cache_key(current_metrics, previous_metrics)
        
        # Factory fonksiyonu (lock içinde çalışacak)
        async def factory():
            return await self._fetch_from_gemini(current_metrics, previous_metrics)
        
        try:
            # ═══════════════════════════════════════════════════════════════
            # DISTRIBUTED LOCKING İLE CACHE KONTROLÜ
            # Aynı anda 50 istek gelse bile sadece 1'i API'ye gider!
            # ═══════════════════════════════════════════════════════════════
            report = await GeminiAnalyzerOrchestrator._cache_service.get_or_set_with_lock(
                key=cache_key,
                model_class=GeminiAnalysisReport,
                factory=factory,
                ttl=self.config.cache_ttl,
                lock_timeout=30,
                lock_blocking_timeout=15.0
            )
            
            # Metrikleri güncelle (cache'te None olabilir)
            report.metrics_analyzed = current_metrics
            return report
            
        except RetryError as e:
            # Tüm retry denemeleri başarısız oldu
            original_error = e.last_attempt.exception()
            error_msg = f"{self.config.max_retries} deneme başarısız: {type(original_error).__name__}"
            print(f"❌ {error_msg}")
            return self.fallback.create_fallback_report(current_metrics, error_msg)
            
        except ResourceExhausted as e:
            # 429 hatası - Retry YAPILMADI (doğru davranış)
            error_msg = f"Google API kota aşıldı (429): {str(e)}"
            print(f"❌ {error_msg}")
            return self.fallback.create_fallback_report(current_metrics, error_msg)
            
        except ParseError as e:
            # Parse hatası
            error_msg = f"Parse hatası: {str(e)}"
            print(f"❌ {error_msg}")
            return self.fallback.create_fallback_report(current_metrics, error_msg)
            
        except Exception as e:
            # Diğer beklenmeyen hatalar (rate limit, network vb.)
            error_msg = str(e)
            print(f"❌ Hata: {error_msg}")
            return self.fallback.create_fallback_report(current_metrics, error_msg)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MONITORING / DEBUG METODLARI
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_cache_stats(self) -> dict:
        """Cache istatistiklerini döndür (debug/monitoring için)"""
        self._ensure_services()
        return await GeminiAnalyzerOrchestrator._cache_service.get_stats()
    
    async def get_rate_limit_status(self, identifier: str = "global") -> dict:
        """Rate limit durumunu döndür"""
        self._ensure_services()
        _, remaining = await GeminiAnalyzerOrchestrator._rate_limiter.is_allowed(identifier)
        reset_time = await GeminiAnalyzerOrchestrator._rate_limiter.get_reset_time(identifier)
        
        return {
            "identifier": identifier,
            "remaining": remaining + 1,  # is_allowed bir hak kullandı, geri ekle
            "max_requests": self.config.rate_limit_max,
            "reset_in_seconds": reset_time,
            "window_seconds": self.config.rate_limit_window
        }
    
    async def invalidate_cache(self, pattern: str = "*") -> int:
        """Cache'i temizle (threshold değişikliğinde kullanılır)"""
        self._ensure_services()
        deleted = await GeminiAnalyzerOrchestrator._cache_service.clear_prefix(pattern)
        print(f"🗑️ {deleted} cache entry silindi")
        return deleted
