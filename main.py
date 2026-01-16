"""
FastAPI Model Server - Ana Uygulama
Modüler yapı ile refactored
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from models.dummy_model import ml_model

# Router imports
from routes.health import router as health_router
from routes.predict import router as predict_router
from routes.analytics import router as analytics_router

# FastAPI uygulaması oluştur
app = FastAPI(
    title="FastAPI Model Server",
    description="ML Model Serving ve Performans İzleme API'si",
    version="4.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Router'ları kaydet
app.include_router(health_router)
app.include_router(predict_router)
app.include_router(analytics_router)


# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Uygulama başlatıldığında çalışır"""
    print("=" * 50)
    print("🚀 FastAPI Model Server başlatılıyor...")
    print("=" * 50)
    
    # ML modelini yükle
    ml_model.load_model()
    
    print("=" * 50)
    print("✅ Sunucu hazır!")
    print("📖 Dokümantasyon: http://localhost:8000/docs")
    print("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """Uygulama kapatıldığında çalışır"""
    print("🔴 Sunucu kapatılıyor...")


# ============================================================================
# HATA YÖNETİMİ
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Özel 404 hata mesajı"""
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Aradığınız endpoint bulunamadı",
            "available_endpoints": ["/", "/health", "/predict", "/metrics/aggregated", "/analyze/performance"],
            "documentation": "/docs"
        }
    )
