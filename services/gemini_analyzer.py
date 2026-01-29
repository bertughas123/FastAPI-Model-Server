"""
Gemini API ile Performans Analizi Servisi
Redis Tabanlı Cache ve Rate Limiting + Tenacity Resilience

Özellikler:
- Cache-First Pattern: Önce Redis cache kontrol edilir
- Global Rate Limiting: Tüm worker'lar aynı sayacı paylaşır
- Fallback: API hatalarında kural tabanlı analiz
- Lazy Initialization: Redis servisleri ilk çağrıda başlatılır
- Retry Mechanism: Geçici hatalarda Exponential Backoff ile yeniden deneme
"""
import google.generativeai as genai
from typing import Optional
import os
from dotenv import load_dotenv

# Tenacity - Retry mekanizması
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random,
    retry_if_exception_type,
    RetryError
)

# Google API hataları
from google.api_core.exceptions import (
    ServiceUnavailable,      # 503 - Geçici, retry mantıklı
    DeadlineExceeded,        # Timeout - Geçici, retry mantıklı
    InternalServerError,     # 500 - Bazen geçici
    ResourceExhausted,       # 429 - Rate limit (retry YAPMA!)
)

from schemas.metrics import (
    AggregatedMetrics,
    GeminiAnalysisReport,
    PerformanceIssue,
)
from database.redis_connection import RedisManager
from core.redis_rate_limiter import RedisRateLimiter
from services.redis_cache import RedisCacheService

load_dotenv()


class GeminiAnalyzerRedis:
    """
    Gemini API kullanarak metrik analizi yapan sınıf
    
    Redis Entegrasyonu:
    - Cache: Aynı metrikler için tekrar API çağrısı yapma
    - Rate Limit: Global API kota koruması (Sliding Window)
    
    Resilience (Tenacity):
    - Geçici hatalarda (503, 500, Timeout) 4 deneme
    - Exponential Backoff + Jitter
    - 429 (ResourceExhausted) retry YAPILMAZ
    
    Akış:
    1. Cache kontrolü (HIT → direkt döndür, rate limit artmaz)
    2. Rate limit kontrolü (MISS → limit check)
    3. API isteği (Retry korumalı)
    4. Cache'e kaydet
    """
    
    # Class-level services (singleton pattern)
    _rate_limiter: Optional[RedisRateLimiter] = None
    _cache_service: Optional[RedisCacheService] = None
    
    def __init__(self):
        """API key ile Gemini'yi yapılandır"""
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key or api_key == "your_api_key_here":
            print("⚠️  GEMINI_API_KEY bulunamadı! .env dosyasını kontrol edin.")
            print("   API key almak için: https://aistudio.google.com/app/apikey")
            self.model = None
            return
        
        # Gemini yapılandırması
        genai.configure(api_key=api_key)
        
        # Model konfigürasyonu (.env'den okunur)
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))
        self.max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "1024"))
        
        # Model instance (Native JSON Mode - 0.4.0+ gerektirir)
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
                "response_mime_type": "application/json",  # Native JSON mode
            }
        )
        
        # Rate Limit ayarları
        self.rate_limit_max = int(os.getenv("GEMINI_RATE_LIMIT", "10"))
        self.rate_limit_window = 60  # 1 dakika (Sliding Window)
        
        # Cache ayarları
        self.cache_ttl = int(os.getenv("GEMINI_CACHE_TTL", "300"))  # 5 dakika
        
        # Retry ayarları
        self.max_retries = 4  # Toplam deneme sayısı
        
        print(f"✅ Gemini Analyzer (Redis + Tenacity) hazır")
        print(f"   Model: {self.model_name}")
        print(f"   Rate Limit: {self.rate_limit_max} req/min (Global)")
        print(f"   Cache TTL: {self.cache_ttl}s")
        print(f"   Retry: {self.max_retries} deneme (Exponential Backoff)")
    
    def _ensure_services(self) -> None:
        """
        Redis servislerinin başlatıldığından emin ol (Lazy Initialization)
        
        Neden lazy?
        - __init__ sırasında Redis bağlantısı olmayabilir
        - Servisleri sadece gerçekten ihtiyaç duyulduğunda başlat
        - Singleton pattern ile tekrar yaratmayı önle
        """
        if GeminiAnalyzerRedis._rate_limiter is None:
            redis_client = RedisManager.get_client()
            
            # Global rate limiter (tüm worker'lar paylaşır)
            GeminiAnalyzerRedis._rate_limiter = RedisRateLimiter(
                redis_client=redis_client,
                key_prefix="gemini_ratelimit",
                max_requests=self.rate_limit_max,
                window_seconds=self.rate_limit_window
            )
            
            # Cache servisi
            GeminiAnalyzerRedis._cache_service = RedisCacheService(
                redis_client=redis_client,
                key_prefix="gemini_cache",
                default_ttl=self.cache_ttl
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
            time=current.time_window_end.isoformat()[:16],  # Dakika hassasiyeti
            prev_total=previous.total_predictions if previous else 0
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RETRY KORUMASLI API ÇAĞRISI
    # ═══════════════════════════════════════════════════════════════════════════
    
    @retry(
        stop=stop_after_attempt(4),  # Maksimum 4 deneme
        wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),  # Exp backoff + jitter
        retry=retry_if_exception_type((
            ServiceUnavailable,      # 503 - Geçici, retry mantıklı
            DeadlineExceeded,        # Timeout - Geçici, retry mantıklı
            InternalServerError,     # 500 - Bazen geçici
            ConnectionError,         # Network - Geçici
            TimeoutError,            # Python timeout - Geçici
        )),
        # ❌ ResourceExhausted (429) burada YOK - Redis rate limit zaten var
        before_sleep=lambda retry_state: print(
            f"⏳ Retry #{retry_state.attempt_number} - "
            f"Bekleniyor: {retry_state.next_action.sleep:.1f}s"
        )
    )
    async def _call_gemini_api(self, prompt: str) -> str:
        """
        Gemini API'ye istek at (Native Async + Retry korumalı)
        
        google-generativeai 0.8.6+ sürümünde generate_content_async()
        native async desteği sağlar. Event loop'u bloklamaz.
        
        Retry edilecek hatalar:
        - 503 ServiceUnavailable
        - 500 InternalServerError
        - DeadlineExceeded (Timeout)
        - ConnectionError
        - TimeoutError
        
        Retry EDİLMEYECEK hatalar:
        - 429 ResourceExhausted (Redis rate limit var)
        - 400 InvalidArgument (düzeltilmesi gereken hata)
        - 401/403 Authentication (retry ile düzelmez)
        
        Args:
            prompt: Gemini'ye gönderilecek prompt
            
        Returns:
            str: Gemini'nin yanıt metni
            
        Raises:
            RetryError: Tüm denemeler başarısız olduysa
            ResourceExhausted: 429 hatası (retry yapılmadan)
            Diğer Exception'lar: Retry dışı hatalar
        """
        # Native async API çağrısı (google-generativeai 0.8.6+)
        response = await self.model.generate_content_async(prompt)
        return response.text
    
    async def _fetch_from_gemini(
        self,
        current_metrics: AggregatedMetrics,
        previous_metrics: Optional[AggregatedMetrics]
    ) -> GeminiAnalysisReport:
        """
        Gemini'den rapor al (Rate Limit + API + Parse)
        
        Bu factory fonksiyonu get_or_set_with_lock içinde çağrılır.
        Lock içinde çalışır, yani sadece 1 istek API'ye gider.
        
        ╔═══════════════════════════════════════════════════════════════════╗
        ║ FACTORY PATTERN                                                    ║
        ╠═══════════════════════════════════════════════════════════════════╣
        ║ Bu method şunları yapıyor:                                        ║
        ║ 1. Rate limit kontrolü                                            ║
        ║ 2. Prompt oluşturma                                               ║
        ║ 3. API çağrısı (Retry korumalı)                                   ║
        ║ 4. Response parsing                                               ║
        ║                                                                    ║
        ║ Lock içinde çağrıldığı için Cache Stampede olmaz!                 ║
        ╚═══════════════════════════════════════════════════════════════════╝
        
        Args:
            current_metrics: Güncel metrikler
            previous_metrics: Karşılaştırma için önceki metrikler
            
        Returns:
            GeminiAnalysisReport: Analiz raporu
            
        Raises:
            Exception: Rate limit aşıldıysa veya API hatası
        """
        # Rate limit kontrolü
        allowed, remaining = await GeminiAnalyzerRedis._rate_limiter.is_allowed("global")
        
        if not allowed:
            reset_time = await GeminiAnalyzerRedis._rate_limiter.get_reset_time("global")
            raise Exception(
                f"Global rate limit aşıldı ({self.rate_limit_max}/dk). "
                f"Yeniden deneme: {reset_time} saniye"
            )
        
        print(f"🚦 Rate limit OK. Kalan: {remaining}")
        
        # Prompt oluştur
        prompt = self._build_analysis_prompt(current_metrics, previous_metrics)
        
        # API çağrısı (Retry korumalı)
        response_text = await self._call_gemini_api(prompt)
        
        # Parse et
        report = self._parse_gemini_response(response_text, current_metrics)
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
        
        Akış (get_or_set_with_lock):
        1. Cache kontrolü (HIT → direkt döndür)
        2. Lock edin (sadece 1 istek API'ye gider)
        3. Double-check cache (biri yazmış olabilir)
        4. Factory çalıştır (rate limit + API + parse)
        5. Cache'e kaydet
        6. Lock serbest bırak
        """
        if not self.model:
            return self._create_fallback_report(
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
            report = await GeminiAnalyzerRedis._cache_service.get_or_set_with_lock(
                key=cache_key,
                model_class=GeminiAnalysisReport,
                factory=factory,
                ttl=self.cache_ttl,
                lock_timeout=30,
                lock_blocking_timeout=15.0
            )
            
            # Metrikleri güncelle (cache'te None olabilir)
            report.metrics_analyzed = current_metrics
            return report
            
        except RetryError as e:
            # Tüm retry denemeleri başarısız oldu
            original_error = e.last_attempt.exception()
            error_msg = f"{self.max_retries} deneme başarısız: {type(original_error).__name__}"
            print(f"❌ {error_msg}")
            return self._create_fallback_report(current_metrics, error_msg)
            
        except ResourceExhausted as e:
            # 429 hatası - Retry YAPILMADI (doğru davranış)
            error_msg = f"Google API kota aşıldı (429): {str(e)}"
            print(f"❌ {error_msg}")
            return self._create_fallback_report(current_metrics, error_msg)
            
        except Exception as e:
            # Diğer beklenmeyen hatalar (rate limit, parse error vb.)
            error_msg = str(e)
            print(f"❌ Hata: {error_msg}")
            return self._create_fallback_report(current_metrics, error_msg)
    
    def _build_analysis_prompt(
        self,
        current: AggregatedMetrics,
        previous: Optional[AggregatedMetrics]
    ) -> str:
        """Gemini için detaylı analiz prompt'u oluştur"""
        
        prompt = f"""Sen bir Machine Learning Model Performance Analyst'sın.
Bir sentiment analiz modelinin performans metriklerini analiz etmelisin.

## GÜNCEL METRİKLER ({current.time_window_start} - {current.time_window_end})
- Toplam Tahmin Sayısı: {current.total_predictions}
- Ortalama Güven Skoru: {current.average_confidence:.2f}
- Ortalama Gecikme: {current.average_inference_time_ms:.2f}ms
- P95 Gecikme: {current.p95_inference_time_ms:.2f}ms
- Min/Max Gecikme: {current.min_inference_time_ms:.2f}ms / {current.max_inference_time_ms:.2f}ms
- Sentiment Dağılımı: {dict(current.sentiment_distribution)}
- Durum: {current.status.value}
"""
        
        # Önceki metriklerle karşılaştırma
        if previous and previous.total_predictions > 0:
            conf_change = ((current.average_confidence - previous.average_confidence) 
                          / previous.average_confidence * 100)
            
            # P95 Gecikme Değişimi (tail latency analizi için daha profesyonel)
            # Fallback: p95 değeri None veya 0 ise hesaplama yapma
            if (previous.p95_inference_time_ms and previous.p95_inference_time_ms > 0 and
                current.p95_inference_time_ms and current.p95_inference_time_ms > 0):
                p95_latency_change = ((current.p95_inference_time_ms - previous.p95_inference_time_ms)
                                     / previous.p95_inference_time_ms * 100)
                p95_change_text = f"{p95_latency_change:+.1f}%"
            else:
                p95_change_text = "Hesaplanamadı (yetersiz veri)"
            
            prompt += f"""
## ÖNCEKİ DÖNEM İLE KARŞILAŞTIRMA
- Güven Skoru Değişimi: {conf_change:+.1f}%
- P95 Gecikme Değişimi: {p95_change_text}
- Tahmin Sayısı Farkı: {current.total_predictions - previous.total_predictions:+d}
"""
        
        prompt += """
## GÖREV
Aşağıdaki JSON formatında bir analiz raporu oluştur:

```json
{
  "summary": "2-3 cümlelik özet",
  "identified_issues": [
    {
      "issue_type": "low_confidence | high_latency | data_drift",
      "severity": "low | medium | high | critical",
      "description": "Sorun açıklaması"
    }
  ],
  "recommendations": [
    "Öneri 1",
    "Öneri 2"
  ],
  "root_cause_hypothesis": "Kök neden hakkında hipotez",
  "confidence_score": 0.0-1.0 (bu analizine ne kadar güveniyorsun)
}
```

ÖNEMLİ:
- Yanıtını SADECE JSON olarak ver, başka metin ekleme
- identified_issues boş liste olabilir (sorun yoksa)
- Türkçe yaz
- Somut, actionable öneriler ver
- Eğer metrik sayısı çok azsa (< 5), bunu belirt
"""
        
        return prompt
    
    def _parse_gemini_response(
        self,
        response_text: str,
        metrics: AggregatedMetrics
    ) -> GeminiAnalysisReport:
        """
        Gemini'nin JSON yanıtını Pydantic ile parse et (Native JSON Mode)
        
        response_mime_type="application/json" sayesinde Gemini doğrudan
        JSON döner, manuel string parsing'e gerek yok.
        """
        try:
            # Pydantic native JSON validation
            report = GeminiAnalysisReport.model_validate_json(response_text)
            
            # Metrik bilgisini manuel olarak ekle (Gemini bunu bilmiyor)
            report.metrics_analyzed = metrics
            
            return report
            
        except Exception as e:
            print(f"⚠️ Gemini yanıtı parse edilemedi: {e}")
            print(f"Yanıt: {response_text[:200]}...")
            return self._create_fallback_report(metrics, f"Parse hatası: {str(e)}")
    
    def _create_fallback_report(
        self,
        metrics: AggregatedMetrics,
        error_msg: str
    ) -> GeminiAnalysisReport:
        """
        Hata durumunda kural tabanlı varsayılan rapor oluştur
        
        Tetiklenme durumları:
        - Rate limit aşıldı
        - API hatası (tüm retry'lar başarısız)
        - Parse hatası
        - API key yok
        - 429 ResourceExhausted
        """
        issues = []
        recommendations = []
        
        # Düşük güven kontrolü
        if metrics.average_confidence < 0.6:
            issues.append(PerformanceIssue(
                issue_type="low_confidence",
                severity="high",
                description=f"Ortalama güven skoru düşük: {metrics.average_confidence:.2f}"
            ))
            recommendations.append("Model yeniden eğitimi düşünün")
        
        # Yüksek gecikme kontrolü
        if metrics.average_inference_time_ms > 200:
            issues.append(PerformanceIssue(
                issue_type="high_latency",
                severity="medium",
                description=f"Ortalama gecikme yüksek: {metrics.average_inference_time_ms:.2f}ms"
            ))
            recommendations.append("Sunucu kaynaklarını kontrol edin")
        
        # Yetersiz veri kontrolü
        if metrics.total_predictions < 5:
            summary = f"Yetersiz veri: Sadece {metrics.total_predictions} tahmin var. Daha fazla veri toplanmalı."
        else:
            summary = f"Otomatik analiz: {len(issues)} sorun tespit edildi. (Hata: {error_msg})"
        
        return GeminiAnalysisReport(
            summary=summary,
            identified_issues=issues,
            recommendations=recommendations if recommendations else ["Daha fazla veri toplayın"],
            root_cause_hypothesis="Gemini API kullanılamadığı için kural tabanlı analiz yapıldı",
            confidence_score=0.3,
            metrics_analyzed=metrics
        )
    
    async def get_cache_stats(self) -> dict:
        """Cache istatistiklerini döndür (debug/monitoring için)"""
        self._ensure_services()
        return await GeminiAnalyzerRedis._cache_service.get_stats()
    
    async def get_rate_limit_status(self, identifier: str = "global") -> dict:
        """Rate limit durumunu döndür"""
        self._ensure_services()
        _, remaining = await GeminiAnalyzerRedis._rate_limiter.is_allowed(identifier)
        reset_time = await GeminiAnalyzerRedis._rate_limiter.get_reset_time(identifier)
        
        return {
            "identifier": identifier,
            "remaining": remaining + 1,  # is_allowed bir hak kullandı, geri ekle
            "max_requests": self.rate_limit_max,
            "reset_in_seconds": reset_time,
            "window_seconds": self.rate_limit_window
        }
    
    async def invalidate_cache(self, pattern: str = "*") -> int:
        """Cache'i temizle (threshold değişikliğinde kullanılır)"""
        self._ensure_services()
        deleted = await GeminiAnalyzerRedis._cache_service.clear_prefix(pattern)
        print(f"🗑️ {deleted} cache entry silindi")
        return deleted


# ═══════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY
# Eski kod `gemini_analyzer` kullanıyorsa çalışmaya devam etsin
# ═══════════════════════════════════════════════════════════════════════════

# Global instance (yeni sınıf)
gemini_analyzer = GeminiAnalyzerRedis()

# Legacy alias (eski import'lar için)
GeminiAnalyzer = GeminiAnalyzerRedis
