"""
Sağlık ve Genel Endpoint'ler
/ ve /health rotaları için APIRouter
"""
from fastapi import APIRouter, status
from datetime import datetime
import time

from schemas.responses import HealthResponse
from models.dummy_model import ml_model

router = APIRouter(tags=["Health"])

# Uygulama başlangıç zamanı (uptime hesabı için)
app_start_time = time.time()


@router.get(
    "/",
    summary="Ana Sayfa",
    description="API'nin çalıştığını doğrular"
)
async def root():
    """Ana endpoint - API'nin çalıştığını gösterir"""
    return {
        "message": "FastAPI Model Server çalışıyor! 🚀",
        "documentation": "/docs",
        "health_check": "/health"
    }


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Sağlık Kontrolü",
    description="Servis ve model durumunu kontrol eder",
    status_code=status.HTTP_200_OK
)
async def health_check():
    """
    Sağlık kontrolü endpoint'i
    
    Returns:
        HealthResponse: Servis durumu bilgileri
    """
    uptime = time.time() - app_start_time
    
    return HealthResponse(
        status="healthy" if ml_model.is_loaded else "unhealthy",
        model_loaded=ml_model.is_loaded,
        model_name=ml_model.model_name,
        model_version=ml_model.version,
        timestamp=datetime.utcnow().isoformat() + "Z",
        uptime_seconds=round(uptime, 2)
    )
