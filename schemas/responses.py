"""
Yanıt Şemaları (Response Schemas) - Generic AI Platform
API'den dönen verilerin yapısı
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from schemas.metrics import PredictionMetric


class PredictResponse(BaseModel):
    """Tahmin yanıtı için veri modeli (Generic)"""
    
    # ════════════════════════════════════════════════════════════════
    # GENERIC FIELDS
    # ════════════════════════════════════════════════════════════════
    
    prediction_label: Optional[str] = Field(
        default=None,
        description="Tahmin edilen etiket (Positive, Spam, TR vb.)"
    )
    
    task_type: str = Field(
        default="classification",
        description="Görev tipi"
    )
    
    model_name: Optional[str] = Field(
        default=None,
        description="Kullanılan model adı"
    )
    
    # ════════════════════════════════════════════════════════════════
    # PERFORMANCE METRICS
    # ════════════════════════════════════════════════════════════════
    
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Tahmin güven skoru"
    )
    
    inference_time_ms: float = Field(
        description="Model çıkarım süresi (ms)"
    )
    
    timestamp: str = Field(
        description="İstek zamanı (ISO 8601)"
    )
    
    model_version: str = Field(
        description="Model versiyonu"
    )
    
    # ════════════════════════════════════════════════════════════════
    # OPTIONAL DETAILED DATA
    # ════════════════════════════════════════════════════════════════
    
    metric: Optional[PredictionMetric] = Field(
        None,
        description="Detaylı metrik bilgisi (include_metrics=True ise)"
    )
    
    raw_output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Modelin ham çıktısı (logits, scores vb.) - debugging için"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "prediction_label": "Positive",
                    "task_type": "classification",
                    "model_name": "SentimentModel",
                    "confidence": 0.87,
                    "inference_time_ms": 45.2,
                    "timestamp": "2024-01-10T10:30:00Z",
                    "model_version": "1.0.0",
                    "raw_output": {
                        "logits": [0.87, 0.08, 0.05],
                        "labels": ["Positive", "Negative", "Neutral"]
                    }
                },
                {
                    "prediction_label": "Spam",
                    "task_type": "classification",
                    "model_name": "SpamDetector",
                    "confidence": 0.95,
                    "inference_time_ms": 38.1,
                    "timestamp": "2024-01-10T10:31:00Z",
                    "model_version": "2.0.0",
                    "raw_output": {
                        "spam_score": 0.95,
                        "keywords": ["free", "winner", "click"]
                    }
                }
            ]
        }


class HealthResponse(BaseModel):
    """Sağlık kontrolü yanıtı"""
    
    status: str = Field(description="Servis durumu")
    model_loaded: bool = Field(description="Model yüklenme durumu")
    model_name: str = Field(description="Model adı")
    model_version: str = Field(description="Model versiyonu")
    timestamp: str = Field(description="Kontrol zamanı")
    uptime_seconds: float = Field(description="Servis çalışma süresi (saniye)")
