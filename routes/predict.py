"""
Tahmin Endpoint'leri - PostgreSQL Entegrasyonu
"""
from fastapi import APIRouter, HTTPException, status, Request, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from database.connection import get_db
from services.metrics_tracker_db import MetricsTrackerDB
from core.rate_limiter_db import RateLimiterDB

from schemas.requests import PredictRequest
from schemas.responses import PredictResponse
from models.dummy_model import ml_model

router = APIRouter(prefix="/predict", tags=["Predictions"])


# Dependency Factory Functions
async def get_metrics_tracker(db: AsyncSession = Depends(get_db)):
    """Her request için yeni tracker"""
    return MetricsTrackerDB(db)


async def get_rate_limiter(db: AsyncSession = Depends(get_db)):
    """Her request için yeni limiter"""
    return RateLimiterDB(db, max_requests=10, time_window=60)


@router.post("", response_model=PredictResponse)
async def predict(
    request: PredictRequest,
    http_request: Request,
    response: Response,
    rate_limiter: RateLimiterDB = Depends(get_rate_limiter),
    metrics_tracker: MetricsTrackerDB = Depends(get_metrics_tracker)
):
    """ML model tahmini (Async DB)"""
    
    client_ip = http_request.client.host
    
    # Async rate limit kontrolü
    if not await rate_limiter.is_allowed(client_ip, endpoint="/predict"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit aşıldı"
        )
    
    # Model kontrolü
    if not ml_model.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model yüklenmedi"
        )
    
    # Tahmin
    prediction = ml_model.predict(request.text)
    
    # Async metrik kaydet
    metric = await metrics_tracker.add_metric(
        sentiment=prediction["sentiment"],
        confidence=prediction["confidence"],
        inference_time_ms=prediction["inference_time_ms"],
        input_length=len(request.text),
        model_version=ml_model.version
    )
    
    # Rate limit header'ları ekle
    remaining = await rate_limiter.get_remaining_requests(client_ip)
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Window"] = f"{rate_limiter.time_window}s"
    
    return PredictResponse(
        sentiment=prediction["sentiment"],
        confidence=prediction["confidence"],
        inference_time_ms=prediction["inference_time_ms"],
        timestamp=datetime.utcnow().isoformat() + "Z",
        model_version=ml_model.version,
        metric=None  # Opsiyonel
    )
