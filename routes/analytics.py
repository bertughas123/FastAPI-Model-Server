"""
Analiz ve Metrik Endpoint'leri - PostgreSQL Entegrasyonu
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
    """Her request için yeni tracker"""
    return MetricsTrackerDB(db)


async def get_analytics_limiter(db: AsyncSession = Depends(get_db)):
    """Analytics için rate limiter (3 istek/dakika)"""
    return RateLimiterDB(db, max_requests=3, time_window=60)


async def check_analytics_rate_limit(
    request: Request,
    limiter: RateLimiterDB = Depends(get_analytics_limiter)
):
    """Gemini analiz endpoint'i için rate limit kontrolü"""
    client_ip = request.client.host
    
    if not await limiter.is_allowed(client_ip, endpoint="/analyze/performance"):
        remaining = await limiter.get_remaining_requests(client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit aşıldı. Dakikada maksimum 3 analiz isteği yapabilirsiniz. Kalan: {remaining}"
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
# GEMİNİ AI ANALİZ ENDPOİNTİ (Rate Limited)
# ============================================================================

@router.post(
    "/analyze/performance",
    response_model=GeminiAnalysisReport,
    summary="Gemini ile Performans Analizi (Rate Limited: 3/dk)"
)
async def analyze_performance(
    query: MetricsQueryRequest,
    _rate_limit: None = Depends(check_analytics_rate_limit),
    metrics_tracker: MetricsTrackerDB = Depends(get_metrics_tracker)
):
    """
    Gemini AI kullanarak performans metriklerini analiz et (Async DB)
    
    Rate Limit: Dakikada maksimum 3 istek
    """
    # Güncel metrikler
    current_metrics = await metrics_tracker.get_aggregated_metrics(
        time_window_minutes=query.time_window_minutes
    )
    
    # Önceki dönem metrikleri (karşılaştırma için)
    previous_metrics = await metrics_tracker.get_aggregated_metrics(
        time_window_minutes=query.time_window_minutes * 2
    )
    
    # Gemini ile analiz et
    try:
        report = gemini_analyzer.analyze_performance(
            current_metrics=current_metrics,
            previous_metrics=previous_metrics
        )
        return report
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analiz hatası: {str(e)}"
        )
