"""
Analiz ve Metrik Endpoint'leri
/metrics ve /analyze rotaları için APIRouter
"""
from fastapi import APIRouter, HTTPException, status

from schemas.requests import MetricsQueryRequest
from schemas.metrics import AggregatedMetrics, MetricThresholds, GeminiAnalysisReport
from services.metrics_tracker import metrics_tracker
from services.gemini_analyzer import gemini_analyzer

router = APIRouter(tags=["Analytics"])


# ============================================================================
# METRİK ENDPOİNTLERİ
# ============================================================================

@router.post(
    "/metrics/aggregated",
    response_model=AggregatedMetrics,
    summary="Toplam Metrikleri Getir"
)
async def get_aggregated_metrics(query: MetricsQueryRequest):
    """
    Belirli zaman aralığındaki toplam metrikleri döndür
    
    Args:
        query: Zaman penceresi (dakika cinsinden)
        
    Returns:
        Toplanan metrikler (ortalamalar, dağılımlar, vb.)
    """
    return metrics_tracker.get_aggregated_metrics(
        time_window_minutes=query.time_window_minutes
    )


@router.put(
    "/metrics/thresholds",
    response_model=MetricThresholds,
    summary="Eşik Değerlerini Güncelle"
)
async def update_thresholds(thresholds: MetricThresholds):
    """
    Metrik eşik değerlerini güncelle
    
    Args:
        thresholds: Yeni eşik değerleri
        
    Returns:
        Güncellenen eşik değerleri
    """
    metrics_tracker.update_thresholds(thresholds)
    return thresholds


@router.get(
    "/metrics/count",
    summary="Toplam Metrik Sayısı"
)
async def get_metrics_count():
    """Toplam kaydedilmiş metrik sayısını döndür"""
    return {
        "total_metrics": len(metrics_tracker.metrics),
        "description": "Uygulama başlatıldığından beri kaydedilen toplam tahmin sayısı"
    }


# ============================================================================
# GEMİNİ AI ANALİZ ENDPOİNTİ
# ============================================================================

@router.post(
    "/analyze/performance",
    response_model=GeminiAnalysisReport,
    summary="Gemini ile Performans Analizi"
)
async def analyze_performance(query: MetricsQueryRequest):
    """
    Gemini AI kullanarak performans metriklerini analiz et
    
    İki zaman penceresi karşılaştırılır:
    - Güncel: Son X dakika
    - Önceki: X*2 ile X dakika arası
    
    Args:
        query: Zaman penceresi (dakika cinsinden)
        
    Returns:
        Gemini'nin oluşturduğu analiz raporu
        
    Raises:
        HTTPException: Analiz hatası durumunda
    """
    # Güncel metrikler
    current_metrics = metrics_tracker.get_aggregated_metrics(
        time_window_minutes=query.time_window_minutes
    )
    
    # Önceki dönem metrikleri (karşılaştırma için)
    previous_metrics = metrics_tracker.get_aggregated_metrics(
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
