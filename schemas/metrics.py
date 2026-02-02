"""
ML Model Performans Metrikleri İçin Pydantic Şemaları
Generic AI Platform - Her model tipini destekler
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUM TANIMLARI (Sadece MetricStatus kaldı)
# ============================================================================

class MetricStatus(str, Enum):
    """Metrik durumu"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


# ============================================================================
# METRİK MODELLERİ (Generic)
# ============================================================================

class PredictionMetric(BaseModel):
    """Tek bir tahmin için metrikler (Generic)"""
    
    prediction_id: str = Field(
        description="Benzersiz tahmin tanımlayıcısı (UUID)"
    )
    
    # ════════════════════════════════════════════════════════════════
    # GENERIC FIELDS
    # ════════════════════════════════════════════════════════════════
    
    prediction_label: Optional[str] = Field(
        default=None,
        description="Standartlaştırılmış etiket (Positive, Spam, TR vb.)"
    )
    
    metrics_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Model raw output (logits, probabilities, scores)"
    )
    
    task_type: str = Field(
        default="classification",
        description="Model tipi: classification, regression, embedding"
    )
    
    model_name: Optional[str] = Field(
        default=None,
        description="Model adı (SentimentModel, SpamDetector vb.)"
    )
    
    # ════════════════════════════════════════════════════════════════
    # PERFORMANCE METRICS
    # ════════════════════════════════════════════════════════════════
    
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Güven skoru (0-1 arası)"
    )
    
    inference_time_ms: float = Field(
        gt=0,
        description="Model çıkarım süresi (milisaniye)",
        examples=[45.2, 123.5]
    )
    
    input_length: int = Field(
        ge=1,
        le=10000,
        description="Girdi metninin karakter uzunluğu"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Tahmin zamanı (UTC)"
    )
    
    model_version: str = Field(
        description="Kullanılan model versiyonu",
        examples=["1.0.0", "2.1.3"]
    )
    
    @field_validator('prediction_label')
    @classmethod
    def validate_label(cls, v: Optional[str]) -> Optional[str]:
        """Etiket validasyonu: boşluk ve uzunluk kontrolü"""
        if v is None:
            return v
        
        # Boşluk kontrolü
        if not v.strip():
            raise ValueError('Label cannot be empty or whitespace')
        
        # Uzunluk kontrolü
        if len(v) > 100:
            raise ValueError('Label too long (max 100 chars)')
        
        return v.strip()
    
    @field_validator('model_version')
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """Model versiyonunun semantic versioning formatında olduğunu kontrol et"""
        parts = v.split('.')
        if len(parts) != 3:
            raise ValueError('Model version must be in format: X.Y.Z')
        
        for part in parts:
            if not part.isdigit():
                raise ValueError(f'Invalid version part: {part}')
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "prediction_id": "550e8400-e29b-41d4-a716-446655440000",
                "prediction_label": "Positive",
                "task_type": "classification",
                "model_name": "SentimentModel",
                "confidence": 0.87,
                "inference_time_ms": 45.2,
                "input_length": 32,
                "timestamp": "2024-01-10T10:30:00Z",
                "model_version": "1.0.0",
                "metrics_data": {
                    "logits": [0.87, 0.08, 0.05],
                    "labels": ["Positive", "Negative", "Neutral"]
                }
            }
        }


class AggregatedMetrics(BaseModel):
    """Toplanan metrikler (Generic) - Belirli bir zaman aralığı için"""
    
    total_predictions: int = Field(
        ge=0,
        description="Toplam tahmin sayısı"
    )
    
    average_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Ortalama güven skoru"
    )
    
    average_inference_time_ms: float = Field(
        ge=0,
        description="Ortalama çıkarım süresi"
    )
    
    min_inference_time_ms: float = Field(
        ge=0,
        description="En düşük çıkarım süresi"
    )
    
    max_inference_time_ms: float = Field(
        ge=0,
        description="En yüksek çıkarım süresi"
    )
    
    p95_inference_time_ms: Optional[float] = Field(
        None,
        ge=0,
        description="95. persentil çıkarım süresi (isteklerin %95'i bu sürenin altında)"
    )
    
    # ════════════════════════════════════════════════════════════════
    # GENERIC LABEL DISTRIBUTION
    # ════════════════════════════════════════════════════════════════
    
    label_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Etiket dağılımı (dinamik key'ler)",
        examples=[
            {"Positive": 45, "Negative": 20, "Neutral": 35},
            {"Spam": 12, "Ham": 88},
            {"TR": 70, "EN": 25, "DE": 5}
        ]
    )
    
    # Filtre bilgileri
    task_type: Optional[str] = Field(
        default=None,
        description="Filtrelenen task tipi"
    )
    
    model_name: Optional[str] = Field(
        default=None,
        description="Filtrelenen model adı"
    )
    
    status: MetricStatus = Field(
        default=MetricStatus.NORMAL,
        description="Genel metrik durumu"
    )
    
    time_window_start: datetime = Field(
        description="Metrik toplama başlangıç zamanı"
    )
    
    time_window_end: datetime = Field(
        description="Metrik toplama bitiş zamanı"
    )
    
    @field_validator('label_distribution')
    @classmethod
    def validate_distribution(cls, v: dict) -> dict:
        """Dağılımdaki değerlerin negatif olmamasını kontrol et"""
        for label, count in v.items():
            if count < 0:
                raise ValueError(f'Label count cannot be negative: {label}={count}')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_predictions": 100,
                "average_confidence": 0.78,
                "average_inference_time_ms": 67.5,
                "min_inference_time_ms": 23.1,
                "max_inference_time_ms": 234.2,
                "p95_inference_time_ms": 156.3,
                "label_distribution": {
                    "Positive": 45,
                    "Negative": 20,
                    "Neutral": 35
                },
                "task_type": "classification",
                "model_name": "SentimentModel",
                "status": "normal",
                "time_window_start": "2024-01-10T10:00:00Z",
                "time_window_end": "2024-01-10T11:00:00Z"
            }
        }


class MetricThresholds(BaseModel):
    """Metrik eşik değerleri (Uyarı/Kritik seviyeler)"""
    
    min_confidence_warning: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Düşük güven uyarı eşiği"
    )
    
    min_confidence_critical: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Düşük güven kritik eşiği"
    )
    
    max_inference_time_warning_ms: float = Field(
        default=200.0,
        gt=0,
        description="Yüksek gecikme uyarı eşiği (ms)"
    )
    
    max_inference_time_critical_ms: float = Field(
        default=500.0,
        gt=0,
        description="Yüksek gecikme kritik eşiği (ms)"
    )
    
    @field_validator('min_confidence_critical')
    @classmethod
    def critical_must_be_lower_than_warning(cls, v: float, info) -> float:
        """Kritik eşik, uyarı eşiğinden küçük olmalı"""
        if 'min_confidence_warning' in info.data:
            warning = info.data['min_confidence_warning']
            if v >= warning:
                raise ValueError(
                    f'Critical threshold ({v}) must be lower than warning threshold ({warning})'
                )
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "min_confidence_warning": 0.6,
                "min_confidence_critical": 0.4,
                "max_inference_time_warning_ms": 200.0,
                "max_inference_time_critical_ms": 500.0
            }
        }


# ============================================================================
# GEMİNİ ANALİZ ŞEMALARı
# ============================================================================

class PerformanceIssue(BaseModel):
    """Tespit edilen performans sorunu"""
    
    issue_type: str = Field(
        description="Sorun tipi (low_confidence, high_latency, data_drift, vb.)"
    )
    
    severity: str = Field(
        description="Önem derecesi (low, medium, high, critical)"
    )
    
    description: str = Field(
        description="Sorun açıklaması"
    )
    
    detected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Tespit zamanı"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "issue_type": "low_confidence",
                "severity": "high",
                "description": "Ortalama güven skoru 0.45'e düştü (normal: 0.78)",
                "detected_at": "2024-01-10T10:30:00Z"
            }
        }


class GeminiAnalysisReport(BaseModel):
    """Gemini'nin oluşturduğu analiz raporu"""
    
    summary: str = Field(
        description="Genel analiz özeti (2-3 cümle)"
    )
    
    identified_issues: list[PerformanceIssue] = Field(
        default_factory=list,
        description="Tespit edilen sorunlar listesi"
    )
    
    recommendations: list[str] = Field(
        description="Öneriler listesi"
    )
    
    root_cause_hypothesis: Optional[str] = Field(
        default=None,
        description="Kök neden hipotezi"
    )
    
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Gemini'nin analizine olan güveni (0-1)"
    )
    
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Rapor oluşturulma zamanı"
    )
    
    metrics_analyzed: Optional[AggregatedMetrics] = Field(
        default=None,
        description="Analiz edilen metrikler (Python tarafında eklenir)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "summary": "Son 60 dakikada ortalama güven skoru %23 düştü ve gecikme 2.8x arttı.",
                "identified_issues": [
                    {
                        "issue_type": "low_confidence",
                        "severity": "high",
                        "description": "Ortalama güven skoru 0.45'e düştü (normal: 0.78)",
                        "detected_at": "2024-01-10T10:30:00Z"
                    }
                ],
                "recommendations": [
                    "Yeni gelen veri dağılımını inceleyin",
                    "Model yeniden eğitimi düşünün",
                    "A/B test ile eski model versiyonunu deneyin"
                ],
                "root_cause_hypothesis": "Yeni veri kaynağı modelin eğitim dağılımından farklı özelliklere sahip olabilir.",
                "confidence_score": 0.78,
                "generated_at": "2024-01-10T10:30:00Z"
            }
        }
