"""
ML Model Performans Metrikleri İçin Pydantic Şemaları
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUM TANIMLARI (Sabit değerler)
# ============================================================================

class SentimentType(str, Enum):
    """İzin verilen sentiment değerleri"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class MetricStatus(str, Enum):
    """Metrik durumu"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


# ============================================================================
# METRİK MODELLERİ
# ============================================================================

class PredictionMetric(BaseModel):
    """Tek bir tahmin için metrikler"""
    
    prediction_id: str = Field(
        description="Benzersiz tahmin tanımlayıcısı (UUID gibi)"
    )
    
    sentiment: SentimentType = Field(
        description="Tahmin edilen sentiment"
    )
    
    confidence: float = Field(
        ge=0.0,  # greater than or equal (>=)
        le=1.0,  # less than or equal (<=)
        description="Güven skoru (0-1 arası)"
    )
    
    inference_time_ms: float = Field(
        gt=0,  # greater than (>)
        description="Model çıkarım süresi (milisaniye)",
        examples=[45.2, 123.5]
    )
    
    input_length: int = Field(
        ge=1,
        le=1000,
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
    
    @field_validator('model_version')
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """
        Model versiyonunun semantic versioning formatında olduğunu kontrol et
        Örnek: 1.0.0, 2.3.1
        """
        parts = v.split('.')
        if len(parts) != 3:
            raise ValueError('Model version must be in format: X.Y.Z')
        
        # Her parçanın sayı olduğunu kontrol et
        for part in parts:
            if not part.isdigit():
                raise ValueError(f'Invalid version part: {part}')
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "prediction_id": "550e8400-e29b-41d4-a716-446655440000",
                "sentiment": "positive",
                "confidence": 0.87,
                "inference_time_ms": 45.2,
                "input_length": 32,
                "timestamp": "2024-01-10T10:30:00Z",
                "model_version": "1.0.0"
            }
        }


class AggregatedMetrics(BaseModel):
    """Toplanan metrikler (belirli bir zaman aralığı için)"""
    
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
        gt=0,
        description="Ortalama çıkarım süresi"
    )
    
    min_inference_time_ms: float = Field(
        gt=0,
        description="En düşük çıkarım süresi"
    )
    
    max_inference_time_ms: float = Field(
        gt=0,
        description="En yüksek çıkarım süresi"
    )
    
    p95_inference_time_ms: Optional[float] = Field(
        None,
        gt=0,
        description="95. persentil çıkarım süresi (isteklerin %95'i bu sürenin altında)"
    )
    
    sentiment_distribution: Dict[SentimentType, int] = Field(
        description="Sentiment dağılımı",
        examples=[{
            "positive": 45,
            "negative": 20,
            "neutral": 35
        }]
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
    
    @field_validator('sentiment_distribution')
    @classmethod
    def validate_distribution_sum(cls, v: dict) -> dict:
        """Dağılımdaki değerlerin negatif olmamasını kontrol et"""
        for sentiment, count in v.items():
            if count < 0:
                raise ValueError(f'Sentiment count cannot be negative: {sentiment}={count}')
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
                "sentiment_distribution": {
                    "positive": 45,
                    "negative": 20,
                    "neutral": 35
                },
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
        # Pydantic v2'de `values` yerine `info.data` kullanılır
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
# GEMİNİ ANALİZ ŞEMALARı (Aşama 3)
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
    
    root_cause_hypothesis: str = Field(
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
    
    metrics_analyzed: AggregatedMetrics = Field(
        description="Analiz edilen metrikler"
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
