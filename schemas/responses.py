"""
Yanıt Şemaları (Response Schemas)
API'den dönen verilerin yapısı
"""
from pydantic import BaseModel, Field
from typing import Optional
from schemas.metrics import PredictionMetric, SentimentType


class PredictResponse(BaseModel):
    """Tahmin yanıtı için veri modeli"""
    sentiment: SentimentType = Field(description="Tespit edilen duygu")
    confidence: float = Field(ge=0.0, le=1.0, description="Tahmin güven skoru (0-1 arası)")
    inference_time_ms: float = Field(description="Model çıkarım süresi (milisaniye)")
    timestamp: str = Field(description="İstek zamanı (ISO 8601)")
    model_version: str = Field(description="Kullanılan model versiyonu")
    
    # Opsiyonel metrik bilgisi
    metric: Optional[PredictionMetric] = Field(
        None,
        description="Detaylı metrik bilgisi (include_metrics=True ise)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "sentiment": "positive",
                "confidence": 0.87,
                "inference_time_ms": 45.2,
                "timestamp": "2024-01-10T10:30:00Z",
                "model_version": "1.0.0"
            }
        }


class HealthResponse(BaseModel):
    """Sağlık kontrolü yanıtı"""
    status: str = Field(description="Servis durumu")
    model_loaded: bool = Field(description="Model yüklenme durumu")
    model_name: str = Field(description="Model adı")
    model_version: str = Field(description="Model versiyonu")
    timestamp: str = Field(description="Kontrol zamanı")
    uptime_seconds: float = Field(description="Servis çalışma süresi (saniye)")
