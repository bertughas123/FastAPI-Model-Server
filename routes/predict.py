"""
Tahmin Endpoint'leri
/predict rotası için APIRouter
"""
from fastapi import APIRouter, HTTPException, status, Request
from datetime import datetime

from schemas.requests import PredictRequest
from schemas.responses import PredictResponse
from models.dummy_model import ml_model
from services.metrics_tracker import metrics_tracker
from core.rate_limiter import rate_limiter

router = APIRouter(
    prefix="/predict",
    tags=["Predictions"]
)


@router.post(
    "",
    response_model=PredictResponse,
    summary="Tahmin Yap (Rate Limited)",
    description="Gelen metni analiz eder ve sentiment tahmini yapar. Dakikada maksimum 10 istek.",
    status_code=status.HTTP_200_OK
)
async def predict(request: PredictRequest, http_request: Request):
    """
    ML model tahmini endpoint'i (Rate Limited)
    
    Args:
        request: PredictRequest şemasına uygun istek body'si
        http_request: FastAPI Request objesi (IP adresi için)
        
    Returns:
        PredictResponse: Tahmin sonuçları
        
    Raises:
        HTTPException: 
            - 429: Rate limit aşıldı
            - 503: Model yüklü değil
            - 500: Tahmin hatası
    """
    # Rate limit kontrolü
    client_ip = http_request.client.host
    
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit aşıldı. Dakikada maksimum {rate_limiter.max_requests} istek yapabilirsiniz."
        )
    
    # Model durumu kontrolü
    if not ml_model.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model henüz yüklenmedi. Lütfen daha sonra tekrar deneyin."
        )
    
    try:
        # Model tahmini yap
        prediction = ml_model.predict(request.text)
        
        # Metrik kaydet
        metric = metrics_tracker.add_metric(
            sentiment=prediction["sentiment"],
            confidence=prediction["confidence"],
            inference_time_ms=prediction["inference_time_ms"],
            input_length=len(request.text),
            model_version=ml_model.version
        )
        
        # Yanıtı oluştur
        return PredictResponse(
            sentiment=prediction["sentiment"],
            confidence=prediction["confidence"],
            inference_time_ms=prediction["inference_time_ms"],
            timestamp=datetime.utcnow().isoformat() + "Z",
            model_version=ml_model.version,
            metric=metric if request.include_metrics else None
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tahmin sırasında hata oluştu: {str(e)}"
        )
