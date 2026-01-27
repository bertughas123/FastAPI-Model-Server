"""
Gemini API ile Performans Analizi Servisi
Redis Tabanlı Cache ve Rate Limiting

Özellikler:
- Cache-First Pattern: Önce Redis cache kontrol edilir
- Global Rate Limiting: Tüm worker'lar aynı sayacı paylaşır
- Fallback: API hatalarında kural tabanlı analiz
- Lazy Initialization: Redis servisleri ilk çağrıda başlatılır
"""
import google.generativeai as genai
from typing import Optional
import os
from dotenv import load_dotenv

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
    
    Akış:
    1. Cache kontrolü (HIT → direkt döndür, rate limit artmaz)
    2. Rate limit kontrolü (MISS → limit check)
    3. API isteği
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
        
        print(f"✅ Gemini Analyzer (Redis) hazır")
        print(f"   Model: {self.model_name}")
        print(f"   Rate Limit: {self.rate_limit_max} req/min (Global)")
        print(f"   Cache TTL: {self.cache_ttl}s")
    
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
    
    async def analyze_performance(
        self,
        current_metrics: AggregatedMetrics,
        previous_metrics: Optional[AggregatedMetrics] = None
    ) -> GeminiAnalysisReport:
        """
        Performans metriklerini Gemini ile analiz et
        
        Args:
            current_metrics: Güncel metrikler
            previous_metrics: Karşılaştırma için önceki metrikler (opsiyonel)
            
        Returns:
            GeminiAnalysisReport: Analiz raporu
        
        Akış:
        1. Cache kontrolü (HIT → direkt döndür, rate limit artmaz)
        2. Rate limit kontrolü (MISS → limit check)
        3. API isteği
        4. Cache'e kaydet
        """
        if not self.model:
            return self._create_fallback_report(
                current_metrics,
                "Gemini API key yapılandırılmamış"
            )
        
        # Redis servislerini başlat (lazy)
        self._ensure_services()
        
        # ═══════════════════════════════════════════════════════════════════
        # ADIM 1: CACHE KONTROLÜ
        # Cache HIT → Rate limit artmaz, direkt döndür
        # ═══════════════════════════════════════════════════════════════════
        cache_key = self._generate_cache_key(current_metrics, previous_metrics)
        
        cached_report = await GeminiAnalyzerRedis._cache_service.get(
            cache_key,
            GeminiAnalysisReport
        )
        
        if cached_report:
            print(f"📦 Cache HIT: {cache_key[:8]}...")
            # Metrikleri güncelle (cache'te None olabilir)
            cached_report.metrics_analyzed = current_metrics
            return cached_report
        
        print(f"📭 Cache MISS: {cache_key[:8]}...")
        
        # ═══════════════════════════════════════════════════════════════════
        # ADIM 2: RATE LIMIT KONTROLÜ (Sadece cache miss'te)
        # Bu sayede 100 istek gelse bile sadece 1 API çağrısı yapılır
        # ═══════════════════════════════════════════════════════════════════
        allowed, remaining = await GeminiAnalyzerRedis._rate_limiter.is_allowed("global")
        
        if not allowed:
            reset_time = await GeminiAnalyzerRedis._rate_limiter.get_reset_time("global")
            return self._create_fallback_report(
                current_metrics,
                f"Global rate limit aşıldı ({self.rate_limit_max}/dk). "
                f"Yeniden deneme: {reset_time} saniye"
            )
        
        print(f"🚦 Rate limit OK. Kalan: {remaining}")
        
        # ═══════════════════════════════════════════════════════════════════
        # ADIM 3: API İSTEĞİ
        # ═══════════════════════════════════════════════════════════════════
        try:
            prompt = self._build_analysis_prompt(current_metrics, previous_metrics)
            
            # Gemini API çağrısı (sync - google.generativeai sync'tir)
            response = self.model.generate_content(prompt)
            report = self._parse_gemini_response(response.text, current_metrics)
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Gemini API hatası: {error_msg}")
            return self._create_fallback_report(current_metrics, error_msg)
        
        # ═══════════════════════════════════════════════════════════════════
        # ADIM 4: CACHE'E KAYDET
        # Bir sonraki aynı istek için hazır
        # ═══════════════════════════════════════════════════════════════════
        await GeminiAnalyzerRedis._cache_service.set(
            cache_key,
            report,
            ttl=self.cache_ttl
        )
        print(f"💾 Cache kaydedildi: {cache_key[:8]}... (TTL: {self.cache_ttl}s)")
        
        return report
    
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
        - API hatası
        - Parse hatası
        - API key yok
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
