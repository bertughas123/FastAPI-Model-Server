"""
FastAPI Model Server - Ana Uygulama
Aşama 1: Temel API Mimarisi
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any
import time
from datetime import datetime
from models.dummy_model import ml_model

# FastAPI uygulaması oluştur
app = FastAPI(
    title="FastAPI Model Server",
    description="ML Model Serving ve Performans İzleme API'si",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI: http://localhost:8000/docs
    redoc_url="/redoc"  # ReDoc: http://localhost:8000/redoc
)


# ============================================================================
# PYDANTIC MODELLER (Input/Output Şemaları)
# ============================================================================

class PredictRequest(BaseModel):
    """Tahmin isteği için veri modeli"""
    text: str = Field(
        ...,  # ... = zorunlu alan
        min_length=1,
        max_length=1000,
        description="Analiz edilecek metin",
        examples=["Bu ürün gerçekten harika!"]
    )
    
    class Config:
        # Pydantic v2 için JSON schema örnekleri
        json_schema_extra = {
            "example": {
                "text": "Bu ürün gerçekten harika!"
            }
        }


class PredictResponse(BaseModel):
    """Tahmin yanıtı için veri modeli"""
    sentiment: str = Field(description="Tespit edilen duygu (positive/negative/neutral)")
    confidence: float = Field(description="Tahmin güven skoru (0-1 arası)")
    inference_time_ms: float = Field(description="Model çıkarım süresi (milisaniye)")
    timestamp: str = Field(description="İstek zamanı (ISO 8601)")
    model_version: str = Field(description="Kullanılan model versiyonu")


class HealthResponse(BaseModel):
    """Sağlık kontrolü yanıtı"""
    status: str = Field(description="Servis durumu")
    model_loaded: bool = Field(description="Model yüklenme durumu")
    model_name: str = Field(description="Model adı")
    model_version: str = Field(description="Model versiyonu")
    timestamp: str = Field(description="Kontrol zamanı")
    uptime_seconds: float = Field(description="Servis çalışma süresi (saniye)")


# ============================================================================
# GLOBAL DEĞİŞKENLER
# ============================================================================

# Uygulama başlangıç zamanı (uptime hesabı için)
app_start_time = time.time()


# ============================================================================
# LIFECYCLE EVENTS (Uygulama Yaşam Döngüsü)
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Uygulama başlatıldığında çalışır
    Burada model yükleme, veritabanı bağlantısı gibi işlemler yapılır
    """
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
# API ENDPOINTS
# ============================================================================

@app.get(
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


@app.get(
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
    
    ÖNEMLİ: async def kullanıyoruz çünkü FastAPI bu sayede:
    - Birden fazla /health isteğini aynı anda işleyebilir
    - Sistem kaynaklarını daha verimli kullanır
    - Daha yüksek throughput sağlar
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


@app.post(
    "/predict",
    response_model=PredictResponse,
    summary="Tahmin Yap",
    description="Gelen metni analiz eder ve sentiment tahmini yapar",
    status_code=status.HTTP_200_OK
)
async def predict(request: PredictRequest):
    """
    ML model tahmini endpoint'i
    
    Args:
        request: PredictRequest şemasına uygun istek body'si
        
    Returns:
        PredictResponse: Tahmin sonuçları
        
    Raises:
        HTTPException: Model yüklü değilse 503 hatası döner
    
    ASYNC KULLANIM NEDENİ:
    - Model inference sırasında CPU yoğun işlem yapılırken
    - Diğer istekler beklemek zorunda kalmaz
    - Gerçek production'da bu await model.predict_async() olurdu
    """
    # Model durumu kontrolü
    if not ml_model.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model henüz yüklenmedi. Lütfen daha sonra tekrar deneyin."
        )
    
    try:
        # Model tahmini yap
        # NOT: Gerçek async model için: await model.predict_async(request.text)
        prediction = ml_model.predict(request.text)
        
        # Yanıtı oluştur
        return PredictResponse(
            sentiment=prediction["sentiment"],
            confidence=prediction["confidence"],
            inference_time_ms=prediction["inference_time_ms"],
            timestamp=datetime.utcnow().isoformat() + "Z",
            model_version=ml_model.version
        )
        
    except Exception as e:
        # Hata durumunda 500 Internal Server Error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tahmin sırasında hata oluştu: {str(e)}"
        )


# ============================================================================
# HATA YÖNETİMİ (Error Handlers)
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Özel 404 hata mesajı"""
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Aradığınız endpoint bulunamadı",
            "available_endpoints": ["/", "/health", "/predict"],
            "documentation": "/docs"
        }
    )
