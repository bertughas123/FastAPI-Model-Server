"""
SQLAlchemy ORM Modelleri
Pydantic şemalarından dönüştürülmüştür
"""
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, 
    Enum, ForeignKey, Index, Text
)
from sqlalchemy.orm import relationship
from database.connection import Base
from datetime import datetime
import enum


# ════════════════════════════════════════════════════════════════════
# ENUM TANIMLARI
# ════════════════════════════════════════════════════════════════════

class SentimentTypeDB(enum.Enum):
    """Sentiment değerleri"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class MetricStatusDB(enum.Enum):
    """Metrik durumu"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


# ════════════════════════════════════════════════════════════════════
# MODEL VERSIONS TABLOSU
# ════════════════════════════════════════════════════════════════════

class ModelVersionDB(Base):
    """ML model versiyonları"""
    __tablename__ = "model_versions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), default="DummySentimentAnalyzer")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)
    
    # İlişki: Bu versiyona ait tahminler
    predictions = relationship("PredictionMetricDB", back_populates="model_version")
    
    def __repr__(self):
        return f"<ModelVersion(version='{self.version}', name='{self.name}')>"


# ════════════════════════════════════════════════════════════════════
# PREDICTION METRICS TABLOSU
# ════════════════════════════════════════════════════════════════════

class PredictionMetricDB(Base):
    """Tahmin metrikleri"""
    __tablename__ = "prediction_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    prediction_id = Column(
        String(36), 
        unique=True, 
        nullable=False, 
        index=True,
        comment="UUID formatında benzersiz tahmin ID"
    )
    
    # Foreign Key - Model versiyonu
    model_version_id = Column(
        Integer, 
        ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    sentiment = Column(
        Enum(SentimentTypeDB), 
        nullable=False,
        comment="positive, negative, neutral"
    )
    
    confidence = Column(
        Float, 
        nullable=False,
        comment="0.0 - 1.0 arası güven skoru"
    )
    
    inference_time_ms = Column(
        Float, 
        nullable=False,
        comment="Model çıkarım süresi (ms)"
    )
    
    input_length = Column(
        Integer, 
        nullable=False,
        comment="Girdi metninin karakter uzunluğu"
    )
    
    timestamp = Column(
        DateTime, 
        default=datetime.utcnow, 
        index=True,
        comment="Tahmin zamanı (UTC)"
    )
    
    # İlişki
    model_version = relationship("ModelVersionDB", back_populates="predictions")
    
    # Composite Index
    __table_args__ = (
        Index("ix_metrics_timestamp_sentiment", "timestamp", "sentiment"),
        Index("ix_metrics_confidence", "confidence"),
    )
    
    def __repr__(self):
        return f"<PredictionMetric(id='{self.prediction_id}', sentiment='{self.sentiment.value}')>"


# ════════════════════════════════════════════════════════════════════
# RATE LIMIT ENTRIES TABLOSU
# ════════════════════════════════════════════════════════════════════

class RateLimitEntryDB(Base):
    """IP bazlı rate limit kayıtları"""
    __tablename__ = "rate_limit_entries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    client_ip = Column(
        String(45),  # IPv6 desteği
        nullable=False,
        index=True,
        comment="İstemci IP adresi"
    )
    
    request_timestamp = Column(
        DateTime, 
        default=datetime.utcnow, 
        index=True,
        comment="İstek zamanı"
    )
    
    endpoint = Column(
        String(100),
        nullable=True,
        comment="İstek yapılan endpoint"
    )
    
    # Composite Index
    __table_args__ = (
        Index("ix_ratelimit_ip_timestamp", "client_ip", "request_timestamp"),
    )
    
    def __repr__(self):
        return f"<RateLimitEntry(ip='{self.client_ip}')>"


# ════════════════════════════════════════════════════════════════════
# METRIC THRESHOLDS TABLOSU
# ════════════════════════════════════════════════════════════════════

class MetricThresholdsDB(Base):
    """Metrik eşik değerleri konfigürasyonu"""
    __tablename__ = "metric_thresholds"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    name = Column(
        String(50), 
        unique=True, 
        default="default",
        comment="Konfigürasyon profili adı"
    )
    
    # Güven skoru eşikleri
    min_confidence_warning = Column(Float, default=0.6)
    min_confidence_critical = Column(Float, default=0.4)
    
    # Gecikme eşikleri (ms)
    max_inference_time_warning_ms = Column(Float, default=200.0)
    max_inference_time_critical_ms = Column(Float, default=500.0)
    
    # Metadata
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<MetricThresholds(name='{self.name}')>"
