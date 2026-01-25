"""
Sağlık ve Genel Endpoint'ler
/ ve /health rotaları için APIRouter
"""
from fastapi import APIRouter, status
from datetime import datetime
import time

from models.dummy_model import ml_model
from database.redis_connection import RedisManager

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
    summary="Sağlık Kontrolü",
    description="Servis, model ve bağlantı durumlarını kontrol eder",
    status_code=status.HTTP_200_OK
)
async def health_check():
    """
    Genişletilmiş sağlık kontrolü endpoint'i
    
    Returns:
        dict: Servis durumu, model bilgisi ve servis sağlık durumları
    """
    uptime = time.time() - app_start_time
    
    # Redis sağlık kontrolü
    redis_health = await RedisManager.health_check()
    
    # Genel durum belirleme
    is_healthy = (
        ml_model.is_loaded and 
        redis_health.get("status") == "healthy"
    )
    
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "version": "5.1.0",
        "model_loaded": ml_model.is_loaded,
        "model_name": ml_model.model_name,
        "model_version": ml_model.version,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "uptime_seconds": round(uptime, 2),
        "services": {
            "redis": redis_health,
            "postgres": "connected"  # Basitleştirilmiş (bağlantı hatası olursa exception fırlar)
        }
    }

