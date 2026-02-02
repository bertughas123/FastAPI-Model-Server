"""
İstek Şemaları (Request Schemas) - Generic AI Platform
Pydantic modelleri ile gelen verileri doğrulama
"""
from pydantic import BaseModel, Field
from typing import Optional


class PredictRequest(BaseModel):
    """Tahmin isteği için veri modeli (Generic)"""
    
    text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Analiz edilecek metin",
        examples=["Bu ürün gerçekten harika!"]
    )
    
    include_metrics: bool = Field(
        default=True,
        description="Yanıtta metrik bilgisi dönsün mü?"
    )
    
    # ════════════════════════════════════════════════════════════════
    # GENERIC FIELDS
    # ════════════════════════════════════════════════════════════════
    
    model_name: Optional[str] = Field(
        default=None,
        description="Kullanılacak model (None = varsayılan model)"
    )
    
    task_type: str = Field(
        default="classification",
        description="Beklenen görev tipi: classification, regression, embedding"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "text": "Bu ürün harika!",
                    "include_metrics": True,
                    "model_name": "SentimentModel",
                    "task_type": "classification"
                },
                {
                    "text": "FREE WINNER CLICK NOW!!!",
                    "include_metrics": False,
                    "model_name": "SpamDetector",
                    "task_type": "classification"
                }
            ]
        }


class MetricsQueryRequest(BaseModel):
    """Metrik sorgulama isteği (Generic)"""
    
    time_window_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,
        description="Kaç dakikalık metrikleri getir?"
    )
    
    # ════════════════════════════════════════════════════════════════
    # GENERIC FILTER FIELDS
    # ════════════════════════════════════════════════════════════════
    
    task_type: Optional[str] = Field(
        default=None,
        description="Filtrelenecek görev tipi (None = tümü)"
    )
    
    model_name: Optional[str] = Field(
        default=None,
        description="Belirli bir modele göre filtrele (None = tümü)"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "time_window_minutes": 60,
                    "task_type": "classification",
                    "model_name": "SentimentModel"
                },
                {
                    "time_window_minutes": 120,
                    "task_type": None,
                    "model_name": None
                }
            ]
        }


class ThresholdUpdateRequest(BaseModel):
    """Eşik değeri güncelleme isteği (Model Bazlı)"""
    
    min_confidence_warning: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Düşük güven uyarı eşiği"
    )
    
    min_confidence_critical: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Düşük güven kritik eşiği"
    )
    
    max_inference_time_warning_ms: Optional[float] = Field(
        default=None,
        gt=0,
        description="Yüksek gecikme uyarı eşiği (ms)"
    )
    
    max_inference_time_critical_ms: Optional[float] = Field(
        default=None,
        gt=0,
        description="Yüksek gecikme kritik eşiği (ms)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "min_confidence_warning": 0.7,
                "min_confidence_critical": 0.5,
                "max_inference_time_warning_ms": 150.0,
                "max_inference_time_critical_ms": 400.0
            }
        }
