"""
FastAPI Model Server - Ana Uygulama
Aşama 1: Temel API Mimarisi
"""
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any
from collections import deque, defaultdict
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
# RATE LIMITING SİSTEMİ
# ============================================================================

class RateLimiter:
    """
    IP tabanlı basit rate limiter
    
    Nasıl Çalışır:
    1. Her IP için son isteklerin timestamp'lerini deque'da tutar
    2. Yeni istek geldiğinde eski timestamp'leri temizler (time_window dışındakiler)
    3. Limit aşılmışsa False döner, değilse yeni timestamp ekler ve True döner
    
    Neden deque?
    - deque (double-ended queue) baştan ve sondan O(1) ekleme/silme yapar
    - Liste kullanırsak pop(0) işlemi O(n) olur (yavaş)
    - Eski timestamp'leri soldan silmek çok hızlı: popleft()
    """
    
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        """
        Args:
            max_requests: Zaman penceresi içinde maksimum istek sayısı
            time_window: Zaman penceresi (saniye)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        
        # Her IP için timestamp listesi
        # defaultdict: Yeni IP geldiğinde otomatik boş deque oluşturur
        self.requests: Dict[str, deque] = defaultdict(deque)
    
    def is_allowed(self, client_ip: str) -> bool:
        """
        İsteğin izin verilip verilmeyeceğini kontrol et
        
        Args:
            client_ip: İstemci IP adresi
            
        Returns:
            True: İstek kabul edilebilir
            False: Rate limit aşıldı
        """
        current_time = time.time()
        request_times = self.requests[client_ip]
        
        # Eski timestamp'leri temizle (time_window dışındakiler)
        while request_times and request_times[0] < current_time - self.time_window:
            request_times.popleft()
        
        # Limit kontrolü
        if len(request_times) >= self.max_requests:
            return False  # Limit aşıldı
        
        # Yeni timestamp ekle
        request_times.append(current_time)
        return True


# Global rate limiter instance
# Dakikada maksimum 10 istek (60 saniyede 10)
rate_limiter = RateLimiter(max_requests=10, time_window=60)


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
            - 429: Rate limit aşıldı (dakikada 10 istekten fazla)
            - 503: Model yüklü değil
            - 500: Tahmin hatası
    """
    
    # Rate limit kontrolü
    client_ip = http_request.client.host
    
    if not rate_limiter.is_allowed(client_ip):
        # Limit aşıldı - 429 hatası fırlat
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
        # NOT: Gerçek async model için: await model.predict_async(request.text)
        prediction = ml_model.predict(request.text)
        
        # Yanıtı oluştur ve döndür
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
