"""
Analiz ve Metrik Endpoint'leri - PostgreSQL + Redis Entegrasyonu

Çift Katmanlı Koruma Mimarisi:
1. Ingress (PostgreSQL): Bot/spam koruması (60 req/min per IP)
2. Egress (Redis): API kota koruması (10 req/min global) - GeminiAnalyzerRedis içinde
"""
from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from services.metrics_tracker_db import MetricsTrackerDB
from core.rate_limiter_db import RateLimiterDB
from schemas.requests import MetricsQueryRequest
from schemas.metrics import AggregatedMetrics, MetricThresholds, GeminiAnalysisReport
from services.gemini_analyzer import gemini_analyzer

router = APIRouter(tags=["Analytics"])


# ============================================================================
# DEPENDENCY FACTORIES
# ============================================================================

async def get_metrics_tracker(db: AsyncSession = Depends(get_db)):
    """Her request için yeni metrics tracker"""
    return MetricsTrackerDB(db)


async def get_analytics_limiter(db: AsyncSession = Depends(get_db)):
    """
    Analytics endpoint'leri için rate limiter (Ingress Katmanı)
    
    ╔═══════════════════════════════════════════════════════════════════╗
    ║ NOT: Limit 60 req/min olarak ayarlandı (önceki: 3 req/min)        ║
    ╠═══════════════════════════════════════════════════════════════════╣
    ║ NEDEN GEVŞETİLDİ?                                                 ║
    ║                                                                    ║
    ║ 1. ÇİFT KATMANLI MİMARİ:                                          ║
    ║    • Bu katman (PostgreSQL): Sadece bot/spam engellemesi          ║
    ║    • İkinci katman (Redis): Gerçek API kota koruması (10/dk)      ║
    ║                                                                    ║
    ║ 2. CACHE DAVRANIŞI:                                               ║
    ║    • Gemini servisinde cache HIT olursa → Rate limit artmaz       ║
    ║    • Düşük limit + cache = Meşru kullanıcılar gereksiz engellenir ║
    ║                                                                    ║
    ║ 3. KABA KUVVET KORUMASI:                                          ║
    ║    • 60/dk bir insan için çok fazla (1 istek/saniye)              ║
    ║    • Bot saldırısı için yetersiz (engellenir)                     ║
    ║    • Gerçek koruma Redis global limitinde                         ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """
    return RateLimiterDB(
        db, 
        max_requests=60,   # Gevşetildi: 3 → 60
        time_window=60     # 1 dakika
    )


async def check_analytics_rate_limit(
    request: Request,
    limiter: RateLimiterDB = Depends(get_analytics_limiter)
):
    """
    Ingress rate limit kontrolü (PostgreSQL)
    
    Bu katman sadece kaba kuvvet saldırılarını durdurur.
    Gerçek API koruması GeminiAnalyzerRedis içinde (Redis).
    """
    client_ip = request.client.host
    
    if not await limiter.is_allowed(client_ip, endpoint="/analyze/performance"):
        remaining = await limiter.get_remaining_requests(client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Spam koruması aktif. Dakikada maksimum 60 istek. Kalan: {remaining}",
            headers={"X-Rate-Limit-Layer": "ingress-postgres"}
        )


# ============================================================================
# METRİK ENDPOİNTLERİ
# ============================================================================

@router.post(
    "/metrics/aggregated",
    response_model=AggregatedMetrics,
    summary="Toplam Metrikleri Getir"
)
async def get_aggregated_metrics(
    query: MetricsQueryRequest,
    metrics_tracker: MetricsTrackerDB = Depends(get_metrics_tracker)
):
    """
    Belirli zaman aralığındaki toplam metrikleri döndür (Async DB)
    """
    return await metrics_tracker.get_aggregated_metrics(
        time_window_minutes=query.time_window_minutes
    )


@router.put(
    "/metrics/thresholds",
    response_model=MetricThresholds,
    summary="Eşik Değerlerini Güncelle"
)
async def update_thresholds(
    thresholds: MetricThresholds,
    metrics_tracker: MetricsTrackerDB = Depends(get_metrics_tracker)
):
    """
    Metrik eşik değerlerini güncelle (Async DB)
    """
    # Pydantic model'i dict'e çevir
    threshold_dict = thresholds.model_dump()
    
    # DB'ye kaydet
    updated = await metrics_tracker.update_thresholds(threshold_dict)
    
    # Pydantic model'e geri dönüştür
    return MetricThresholds(
        min_confidence_warning=updated.min_confidence_warning,
        min_confidence_critical=updated.min_confidence_critical,
        max_inference_time_warning_ms=updated.max_inference_time_warning_ms,
        max_inference_time_critical_ms=updated.max_inference_time_critical_ms
    )


@router.get(
    "/metrics/count",
    summary="Toplam Metrik Sayısı"
)
async def get_metrics_count(
    metrics_tracker: MetricsTrackerDB = Depends(get_metrics_tracker)
):
    """Toplam kaydedilmiş metrik sayısını döndür (Async DB)"""
    total = await metrics_tracker.get_total_count()
    
    return {
        "total_metrics": total,
        "description": "Veritabanında kayıtlı toplam tahmin sayısı"
    }


# ============================================================================
# GEMİNİ AI ANALİZ ENDPOİNTİ (Çift Katmanlı Koruma)
# ============================================================================

@router.post(
    "/analyze/performance",
    response_model=GeminiAnalysisReport,
    summary="Gemini ile Performans Analizi",
    description="""
    Performans metriklerini Gemini AI ile analiz eder.
    
    **Koruma Katmanları:**
    1. **Ingress (PostgreSQL):** Spam koruması (60 req/min per IP)
    2. **Egress (Redis):** API kota koruması (10 req/min global)
    
    **Cache Davranışı:**
    - Aynı metrikler için cache'ten döner (rate limit tüketmez)
    - Cache TTL: 5 dakika
    """
)
async def analyze_performance(
    query: MetricsQueryRequest,
    _rate_limit: None = Depends(check_analytics_rate_limit),  # Katman 1: Ingress
    metrics_tracker: MetricsTrackerDB = Depends(get_metrics_tracker)
):
    """
    Gemini AI ile performans analizi (Çift Katmanlı Koruma)
    
    Akış:
    1. Ingress Rate Limit (PostgreSQL) ← Burada geçti
    2. → GeminiAnalyzerRedis.analyze_performance()
       2a. Redis Cache kontrolü
       2b. Redis Rate Limit kontrolü (sadece cache miss)
       2c. Gemini API çağrısı
       2d. Cache'e kaydet
    """
    # Güncel metrikler
    current_metrics = await metrics_tracker.get_aggregated_metrics(
        time_window_minutes=query.time_window_minutes
    )
    
    # Önceki dönem metrikleri (karşılaştırma için)
    previous_metrics = await metrics_tracker.get_aggregated_metrics(
        time_window_minutes=query.time_window_minutes * 2
    )
    
    # Gemini analizi (Redis cache + rate limit içeride)
    try:
        report = await gemini_analyzer.analyze_performance(
            current_metrics=current_metrics,
            previous_metrics=previous_metrics
        )
        return report
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analiz hatası: {str(e)}"
        )
