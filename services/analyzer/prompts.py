"""
Prompt Builder

Gemini API için prompt şablonu oluşturma ve formatlama.
Separation of Concerns: Sadece string manipülasyonu yapar.
"""
from typing import Optional
from schemas.metrics import AggregatedMetrics


class PromptBuilder:
    """
    Gemini API için yapılandırılmış prompt'lar üretir
    
    Sorumluluklar:
    - Şablon yönetimi
    - Metrik formatlama
    - Karşılaştırma metni oluşturma
    - Çıktı şeması tanımlama
    """
    
    SYSTEM_ROLE = "Sen bir Machine Learning Model Performance Analyst'sın."
    
    def build_analysis_prompt(
        self,
        current: AggregatedMetrics,
        previous: Optional[AggregatedMetrics] = None
    ) -> str:
        """
        Metriklerle birlikte tam analiz prompt'u oluştur
        
        Args:
            current: Güncel dönem metrikleri
            previous: Karşılaştırma için önceki dönem (opsiyonel)
            
        Returns:
            str: Gemini'ye gönderilecek tam prompt
        """
        prompt = self._get_system_intro()
        prompt += self._format_current_metrics(current)
        
        if previous and previous.total_predictions > 0:
            prompt += self._format_comparison(current, previous)
        
        prompt += self._get_output_schema()
        
        return prompt
    
    def _get_system_intro(self) -> str:
        """Sistem rolü tanımı"""
        return f"""{self.SYSTEM_ROLE}
Bir sentiment analiz modelinin performans metriklerini analiz etmelisin.

"""
    
    def _format_current_metrics(self, metrics: AggregatedMetrics) -> str:
        """
        Güncel dönem metrik bölümünü formatla
        
        Args:
            metrics: Formatlanacak metrikler
            
        Returns:
            str: Formatlı metrik bölümü
        """
        return f"""## GÜNCEL METRİKLER ({metrics.time_window_start} - {metrics.time_window_end})
- Toplam Tahmin Sayısı: {metrics.total_predictions}
- Ortalama Güven Skoru: {metrics.average_confidence:.2f}
- Ortalama Gecikme: {metrics.average_inference_time_ms:.2f}ms
- P95 Gecikme: {metrics.p95_inference_time_ms:.2f}ms
- Min/Max Gecikme: {metrics.min_inference_time_ms:.2f}ms / {metrics.max_inference_time_ms:.2f}ms
- Sentiment Dağılımı: {dict(metrics.sentiment_distribution)}
- Durum: {metrics.status.value}
"""
    
    def _format_comparison(
        self, 
        current: AggregatedMetrics, 
        previous: AggregatedMetrics
    ) -> str:
        """
        Dönemler arası karşılaştırma bölümünü formatla
        
        Args:
            current: Güncel dönem metrikleri
            previous: Önceki dönem metrikleri
            
        Returns:
            str: Formatlı karşılaştırma bölümü
        """
        # Güven skoru değişimi
        conf_change = ((current.average_confidence - previous.average_confidence) 
                      / previous.average_confidence * 100)
        
        # P95 Gecikme değişimi
        if (previous.p95_inference_time_ms and previous.p95_inference_time_ms > 0 and
            current.p95_inference_time_ms and current.p95_inference_time_ms > 0):
            p95_latency_change = ((current.p95_inference_time_ms - previous.p95_inference_time_ms)
                                 / previous.p95_inference_time_ms * 100)
            p95_change_text = f"{p95_latency_change:+.1f}%"
        else:
            p95_change_text = "Hesaplanamadı (yetersiz veri)"
        
        return f"""
## ÖNCEKİ DÖNEM İLE KARŞILAŞTIRMA
- Güven Skoru Değişimi: {conf_change:+.1f}%
- P95 Gecikme Değişimi: {p95_change_text}
- Tahmin Sayısı Farkı: {current.total_predictions - previous.total_predictions:+d}
"""
    
    def _get_output_schema(self) -> str:
        """
        Beklenen JSON çıktı şemasını döndür
        
        Returns:
            str: JSON şema ve talimatlar
        """
        return """
## GÖREV
Aşağıdaki JSON formatında bir analiz raporu oluştur:

```json
{
  "summary": "2-3 cümlelik özet",
  "identified_issues": [
    {
      "issue_type": "low_confidence | high_latency | data_drift",
      "severity": "low | medium | high | critical",
      "description": "Sorun açıklaması"
    }
  ],
  "recommendations": [
    "Öneri 1",
    "Öneri 2"
  ],
  "root_cause_hypothesis": "Kök neden hakkında hipotez",
  "confidence_score": 0.0-1.0 (bu analizine ne kadar güveniyorsun)
}
```

ÖNEMLİ:
- Yanıtını SADECE JSON olarak ver, başka metin ekleme
- identified_issues boş liste olabilir (sorun yoksa)
- Türkçe yaz
- Somut, actionable öneriler ver
- Eğer metrik sayısı çok azsa (< 5), bunu belirt
"""
