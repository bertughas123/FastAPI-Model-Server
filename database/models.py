"""
SQLAlchemy ORM Modelleri - Generic AI Platform
Herhangi bir ML model tipini destekleyen esnek yapı
"""
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, 
    ForeignKey, Index, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from database.connection import Base
from datetime import datetime
import enum


# ════════════════════════════════════════════════════════════════════
# ENUM TANIMLARI (Sadece MetricStatus kaldı)
# ════════════════════════════════════════════════════════════════════

class MetricStatusDB(enum.Enum):
    """Metrik durumu"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


# ════════════════════════════════════════════════════════════════════
# MODEL VERSIONS TABLOSU
# ════════════════════════════════════════════════════════════════════

class ModelVersionDB(Base):
    """
    ML model adı ve versiyonları
    
    Generic: Aynı versiyon farklı modeller için kullanılabilir.
    Örnek: SentimentModel v1.0.0 ve SpamDetector v1.0.0
    """
    __tablename__ = "model_versions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    version = Column(
        String(20), 
        nullable=False, 
        index=True,
        comment="Semantic version (1.0.0)"
    )
    
    name = Column(
        String(100), 
        nullable=False,
        index=True,
        comment="Model adı (SentimentModel, SpamDetector vb.)"
    )
    
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)
    
    # İlişki: Bu versiyona ait tahminler
    predictions = relationship("PredictionMetricDB", back_populates="model_version")
    
    # Unique Constraint: (name, version) ikilisi benzersiz olmalı
    __table_args__ = (
        UniqueConstraint('name', 'version', name='uq_model_name_version'),
    )
    
    def __repr__(self):
        return f"<ModelVersion(name='{self.name}', version='{self.version}')>"


# ════════════════════════════════════════════════════════════════════
# PREDICTION METRICS TABLOSU (Generic)
# ════════════════════════════════════════════════════════════════════

class PredictionMetricDB(Base):
    """
    Tahmin metrikleri - Generic AI Platform
    
    Hibrit Yaklaşım:
    - prediction_label (String): Hızlı sorgulama için (INDEX)
    - metrics_data (JSONB): Esnek veri saklama için (raw output)
    """
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
    
    # ════════════════════════════════════════════════════════════════
    # GENERIC FIELDS
    # ════════════════════════════════════════════════════════════════
    
    prediction_label = Column(
        String(100), 
        nullable=False, 
        index=True,
        comment="Standartlaştırılmış etiket (Positive, Spam, TR vb.)"
    )
    
    metrics_data = Column(
        JSONB, 
        nullable=True,
        comment="Model raw output: {logits, probabilities, raw_score}"
    )
    
    task_type = Column(
        String(50), 
        nullable=False,
        default="classification",
        index=True,
        comment="Model tipi: classification, regression, embedding"
    )
    
    # ════════════════════════════════════════════════════════════════
    # PERFORMANCE METRICS
    # ════════════════════════════════════════════════════════════════
    
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
    
    # Composite Indexes (Performans optimizasyonu)
    __table_args__ = (
        Index("ix_metrics_label_timestamp", "prediction_label", "timestamp"),
        Index("ix_metrics_task_type", "task_type"),
        Index("ix_metrics_confidence", "confidence"),
    )
    
    def __repr__(self):
        return f"<PredictionMetric(id='{self.prediction_id}', label='{self.prediction_label}')>"


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
# METRIC THRESHOLDS TABLOSU (Model Bazlı)
# ════════════════════════════════════════════════════════════════════

class MetricThresholdsDB(Base):
    """
    Metrik eşik değerleri konfigürasyonu - Model Bazlı
    
    Her model için farklı eşikler tanımlanabilir:
    - SentimentModel: min_confidence_warning = 0.6
    - MedicalDiagnosis: min_confidence_warning = 0.95
    """
    __tablename__ = "metric_thresholds"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    model_name = Column(
        String(100), 
        unique=True, 
        nullable=False,
        default="default",
        comment="Model adı (her model için ayrı eşikler)"
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
        return f"<MetricThresholds(model_name='{self.model_name}')>"
