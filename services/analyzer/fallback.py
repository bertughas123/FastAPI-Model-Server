"""
Fallback Engine

API kullanılamadığında kural tabanlı analiz.
Separation of Concerns: Sadece rule-based logic yapar.
"""
from typing import List
from schemas.metrics import (
    AggregatedMetrics,
    GeminiAnalysisReport,
    PerformanceIssue,
)


class FallbackEngine:
    """
    Kural tabanlı fallback analiz motoru
    
    Sorumluluklar:
    - Eşik tabanlı sorun tespiti
    - Varsayılan öneri üretimi
    - Fallback rapor oluşturma
    
    Tetiklenme durumları:
    - API key yapılandırılmamış
    - Rate limit aşıldı
    - Tüm retry'lar başarısız
    - Parse hatası oluştu
    - 429 ResourceExhausted
    """
    
    # Yapılandırılabilir eşikler
    LOW_CONFIDENCE_THRESHOLD = 0.6
    HIGH_LATENCY_THRESHOLD_MS = 200
    MIN_DATA_POINTS = 5
    
    def create_fallback_report(
        self,
        metrics: AggregatedMetrics,
        error_reason: str
    ) -> GeminiAnalysisReport:
        """
        Kural tabanlı analiz raporu oluştur
        
        Args:
            metrics: Analiz edilecek metrikler
            error_reason: Fallback'e düşme sebebi
            
        Returns:
            GeminiAnalysisReport: Kural tabanlı rapor
        """
        issues = self._detect_issues(metrics)
        recommendations = self._generate_recommendations(issues, metrics)
        summary = self._build_summary(metrics, issues, error_reason)
        
        return GeminiAnalysisReport(
            summary=summary,
            identified_issues=issues,
            recommendations=recommendations,
            root_cause_hypothesis=f"Otomatik analiz (Fallback). Sebep: {error_reason}",
            confidence_score=0.3,  # Düşük güven (kural tabanlı)
            metrics_analyzed=metrics
        )
    
    def _detect_issues(self, metrics: AggregatedMetrics) -> List[PerformanceIssue]:
        """
        Sorun tespiti için eşik kurallarını uygula
        
        Args:
            metrics: Analiz edilecek metrikler
            
        Returns:
            List[PerformanceIssue]: Tespit edilen sorunlar
        """
        issues = []
        
        # Düşük güven kontrolü
        if metrics.average_confidence < self.LOW_CONFIDENCE_THRESHOLD:
            issues.append(PerformanceIssue(
                issue_type="low_confidence",
                severity="high",
                description=f"Ortalama güven skoru düşük: {metrics.average_confidence:.2f}"
            ))
        
        # Yüksek gecikme kontrolü
        if metrics.average_inference_time_ms > self.HIGH_LATENCY_THRESHOLD_MS:
            issues.append(PerformanceIssue(
                issue_type="high_latency",
                severity="medium",
                description=f"Ortalama gecikme yüksek: {metrics.average_inference_time_ms:.2f}ms"
            ))
        
        return issues
    
    def _generate_recommendations(
        self, 
        issues: List[PerformanceIssue],
        metrics: AggregatedMetrics
    ) -> List[str]:
        """
        Tespit edilen sorunlara göre öneriler oluştur
        
        Args:
            issues: Tespit edilen sorunlar
            metrics: Analiz edilen metrikler
            
        Returns:
            List[str]: Öneri listesi
        """
        recommendations = []
        
        for issue in issues:
            if issue.issue_type == "low_confidence":
                recommendations.append("Model yeniden eğitimi düşünün")
            elif issue.issue_type == "high_latency":
                recommendations.append("Sunucu kaynaklarını kontrol edin")
        
        # Varsayılan öneri
        if not recommendations:
            recommendations.append("Daha fazla veri toplayın")
        
        return recommendations
    
    def _build_summary(
        self,
        metrics: AggregatedMetrics,
        issues: List[PerformanceIssue],
        error_reason: str
    ) -> str:
        """
        Rapor özeti oluştur
        
        Args:
            metrics: Analiz edilen metrikler
            issues: Tespit edilen sorunlar
            error_reason: Fallback sebebi
            
        Returns:
            str: Özet metni
        """
        # Yetersiz veri kontrolü
        if metrics.total_predictions < self.MIN_DATA_POINTS:
            return (
                f"Yetersiz veri: Sadece {metrics.total_predictions} tahmin var. "
                f"Daha fazla veri toplanmalı."
            )
        
        return (
            f"Otomatik analiz: {len(issues)} sorun tespit edildi. "
            f"(Hata: {error_reason})"
        )
