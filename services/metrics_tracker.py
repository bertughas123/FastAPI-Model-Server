"""
Metrik Takip Servisi
Tahmin metriklerini toplar ve analiz eder
"""
from typing import List
from datetime import datetime, timedelta
from schemas.metrics import (
    PredictionMetric, 
    AggregatedMetrics, 
    MetricThresholds,
    MetricStatus,
    SentimentType
)
import uuid


class MetricsTracker:
    """Metrik toplama ve analiz sınıfı"""
    
    def __init__(self):
        # Metrikleri bellekte tutuyoruz (production'da veritabanı kullanılır)
        self.metrics: List[PredictionMetric] = []
        self.thresholds = MetricThresholds()
    
    def add_metric(
        self,
        sentiment: str,
        confidence: float,
        inference_time_ms: float,
        input_length: int,
        model_version: str
    ) -> PredictionMetric:
        """
        Yeni bir tahmin metriği ekle
        
        Returns:
            Oluşturulan metrik objesi
        """
        metric = PredictionMetric(
            prediction_id=str(uuid.uuid4()),
            sentiment=SentimentType(sentiment),
            confidence=confidence,
            inference_time_ms=inference_time_ms,
            input_length=input_length,
            timestamp=datetime.utcnow(),
            model_version=model_version
        )
        
        self.metrics.append(metric)
        return metric
    
    def get_aggregated_metrics(
        self,
        time_window_minutes: int = 60
    ) -> AggregatedMetrics:
        """
        Belirli bir zaman aralığı için toplam metrikleri hesapla
        
        Args:
            time_window_minutes: Kaç dakikalık metrikler analiz edilsin
            
        Returns:
            Toplanan metrikler
        """
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=time_window_minutes)
        
        # Zaman aralığındaki metrikleri filtrele
        recent_metrics = [
            m for m in self.metrics
            if m.timestamp >= window_start
        ]
        
        if not recent_metrics:
            # Metrik yoksa boş değerler dön
            return AggregatedMetrics(
                total_predictions=0,
                average_confidence=0.0,
                average_inference_time_ms=0.0,
                min_inference_time_ms=0.0,
                max_inference_time_ms=0.0,
                p95_inference_time_ms=None,
                sentiment_distribution={
                    SentimentType.POSITIVE: 0,
                    SentimentType.NEGATIVE: 0,
                    SentimentType.NEUTRAL: 0
                },
                status=MetricStatus.NORMAL,
                time_window_start=window_start,
                time_window_end=now
            )
        
        # İstatistikleri hesapla
        confidences = [m.confidence for m in recent_metrics]
        inference_times = sorted([m.inference_time_ms for m in recent_metrics])
        
        # Sentiment dağılımı
        sentiment_counts = {
            SentimentType.POSITIVE: 0,
            SentimentType.NEGATIVE: 0,
            SentimentType.NEUTRAL: 0
        }
        for m in recent_metrics:
            sentiment_counts[m.sentiment] += 1
        
        # P95 hesaplama (95. persentil)
        p95_index = int(len(inference_times) * 0.95)
        p95_time = inference_times[p95_index] if p95_index < len(inference_times) else inference_times[-1]
        
        # Ortalamalar
        avg_confidence = sum(confidences) / len(confidences)
        avg_inference_time = sum(inference_times) / len(inference_times)
        
        # Durum belirleme (Eşiklere göre)
        status = self._determine_status(avg_confidence, avg_inference_time)
        
        return AggregatedMetrics(
            total_predictions=len(recent_metrics),
            average_confidence=round(avg_confidence, 2),
            average_inference_time_ms=round(avg_inference_time, 2),
            min_inference_time_ms=round(min(inference_times), 2),
            max_inference_time_ms=round(max(inference_times), 2),
            p95_inference_time_ms=round(p95_time, 2),
            sentiment_distribution=sentiment_counts,
            status=status,
            time_window_start=window_start,
            time_window_end=now
        )
    
    def _determine_status(
        self,
        avg_confidence: float,
        avg_inference_time: float
    ) -> MetricStatus:
        """Metrik durumunu eşiklere göre belirle"""
        
        # Kritik durumlar
        if (avg_confidence <= self.thresholds.min_confidence_critical or
            avg_inference_time >= self.thresholds.max_inference_time_critical_ms):
            return MetricStatus.CRITICAL
        
        # Uyarı durumları
        if (avg_confidence <= self.thresholds.min_confidence_warning or
            avg_inference_time >= self.thresholds.max_inference_time_warning_ms):
            return MetricStatus.WARNING
        
        return MetricStatus.NORMAL
    
    def update_thresholds(self, new_thresholds: MetricThresholds):
        """Eşik değerlerini güncelle"""
        self.thresholds = new_thresholds


# Global instance
metrics_tracker = MetricsTracker()
