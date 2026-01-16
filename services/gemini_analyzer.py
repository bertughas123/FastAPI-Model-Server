"""
Gemini API ile Performans Analizi Servisi
"""
import google.generativeai as genai
from typing import Optional, Dict, Tuple
import os
from dotenv import load_dotenv
from schemas.metrics import (
    AggregatedMetrics,
    GeminiAnalysisReport,
    PerformanceIssue,
    MetricStatus
)
import json
import time
from collections import deque
import hashlib

# .env dosyasını yükle
load_dotenv()


class GeminiAnalyzer:
    """Gemini API kullanarak metrik analizi yapan sınıf"""
    
    def __init__(self):
        """API key ile Gemini'yi yapılandır"""
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key or api_key == "your_api_key_here":
            print("⚠️  GEMINI_API_KEY bulunamadı! .env dosyasını kontrol edin.")
            print("   API key almak için: https://aistudio.google.com/app/apikey")
            self.model = None
            return
        
        # Gemini yapılandırması
        genai.configure(api_key=api_key)
        
        # Model konfigürasyonu
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))
        self.max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "1024"))
        
        # Model instance
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
            }
        )
        
        # Rate Limiting: Dakikada maksimum 5 istek
        self.max_requests_per_minute = 10
        self.request_times: deque = deque(maxlen=self.max_requests_per_minute)
        
        # Basit Cache: Son analiz sonuçlarını 5 dakika sakla
        # Format: {cache_key: (timestamp, report)}
        self.cache: Dict[str, Tuple[float, GeminiAnalysisReport]] = {}
        self.cache_ttl = 300  # 5 dakika
        
        # Retry ayarları
        self.max_retries = 2
        self.retry_delay = 1  # Başlangıç bekleme süresi (saniye)
        
        print(f"✅ Gemini Analyzer hazır (Model: {self.model_name})")
        print(f"   Rate Limit: {self.max_requests_per_minute} req/min | Cache TTL: {self.cache_ttl}s")
    
    
    def analyze_performance(
        self,
        current_metrics: AggregatedMetrics,
        previous_metrics: Optional[AggregatedMetrics] = None
    ) -> GeminiAnalysisReport:
        """
        Performans metriklerini Gemini ile analiz et
        
        Args:
            current_metrics: Güncel metrikler
            previous_metrics: Karşılaştırma için önceki metrikler (opsiyonel)
            
        Returns:
            Gemini'nin oluşturduğu analiz raporu
        """
        if not self.model:
            return self._create_fallback_report(
                current_metrics, 
                "Gemini API key yapılandırılmamış"
            )
        
        # Cache kontrolü
        cache_key = self._generate_cache_key(current_metrics, previous_metrics)
        cached_report = self._get_from_cache(cache_key)
        if cached_report:
            print("📦 Cache'den döndürülüyor")
            return cached_report
        
        # Rate limit kontrolü
        if not self._check_rate_limit():
            return self._create_fallback_report(
                current_metrics,
                f"Rate limit aşıldı (maks {self.max_requests_per_minute} req/min). Lütfen bekleyin."
            )
        
        # Prompt oluştur
        prompt = self._build_analysis_prompt(current_metrics, previous_metrics)
        
        # Retry mekanizması ile istek gönder
        for attempt in range(self.max_retries + 1):
            try:
                # Rate limit için timestamp kaydet
                self.request_times.append(time.time())
                
                # Gemini'ye gönder
                response = self.model.generate_content(prompt)
                
                # Yanıtı parse et
                report = self._parse_gemini_response(
                    response.text,
                    current_metrics
                )
                
                # Cache'e kaydet
                self._save_to_cache(cache_key, report)
                
                return report
                
            except Exception as e:
                error_msg = str(e)
                
                # Quota hatası mı?
                if "429" in error_msg or "quota" in error_msg.lower():
                    print(f"⚠️ Quota hatası - Retry {attempt + 1}/{self.max_retries}")
                    
                    if attempt < self.max_retries:
                        # Exponential backoff
                        wait_time = self.retry_delay * (2 ** attempt)
                        print(f"   {wait_time}s bekleniyor...")
                        time.sleep(wait_time)
                        continue
                
                # Son deneme veya farklı bir hata
                print(f"❌ Gemini hatası: {error_msg}")
                return self._create_fallback_report(current_metrics, error_msg)
        
        # Tüm denemeler başarısız
        return self._create_fallback_report(
            current_metrics,
            "Maksimum retry sayısına ulaşıldı"
        )
    
    def _generate_cache_key(
        self,
        current: AggregatedMetrics,
        previous: Optional[AggregatedMetrics]
    ) -> str:
        """Metrikler için benzersiz cache anahtarı oluştur"""
        # Metrikleri string'e çevir ve hash al
        key_data = f"{current.total_predictions}_{current.average_confidence:.2f}_{current.time_window_end}"
        if previous:
            key_data += f"_{previous.total_predictions}"
        
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[GeminiAnalysisReport]:
        """Cache'den rapor al (varsa ve geçerliyse)"""
        if cache_key in self.cache:
            timestamp, report = self.cache[cache_key]
            
            # TTL kontrolü
            if time.time() - timestamp < self.cache_ttl:
                return report
            else:
                # Expire olmuş, sil
                del self.cache[cache_key]
        
        return None
    
    def _save_to_cache(self, cache_key: str, report: GeminiAnalysisReport):
        """Raporu cache'e kaydet"""
        self.cache[cache_key] = (time.time(), report)
        
        # Cache temizliği (100'den fazla entry varsa eski olanları sil)
        if len(self.cache) > 100:
            # En eski 50'yi sil
            sorted_items = sorted(self.cache.items(), key=lambda x: x[1][0])
            for key, _ in sorted_items[:50]:
                del self.cache[key]
    
    def _check_rate_limit(self) -> bool:
        """Rate limit kontrolü yap"""
        current_time = time.time()
        
        # 60 saniyeden eski istekleri temizle
        while self.request_times and self.request_times[0] < current_time - 60:
            self.request_times.popleft()
        
        # Limit kontrolü
        if len(self.request_times) >= self.max_requests_per_minute:
            return False
        
        return True

    
    def _build_analysis_prompt(
        self,
        current: AggregatedMetrics,
        previous: Optional[AggregatedMetrics]
    ) -> str:
        """Gemini için detaylı analiz prompt'u oluştur"""
        
        prompt = f"""Sen bir Machine Learning Model Performance Analyst'sın.
Bir sentiment analiz modelinin performans metriklerini analiz etmelisin.

## GÜNCEL METRİKLER ({current.time_window_start} - {current.time_window_end})
- Toplam Tahmin Sayısı: {current.total_predictions}
- Ortalama Güven Skoru: {current.average_confidence:.2f}
- Ortalama Gecikme: {current.average_inference_time_ms:.2f}ms
- P95 Gecikme: {current.p95_inference_time_ms:.2f}ms
- Min/Max Gecikme: {current.min_inference_time_ms:.2f}ms / {current.max_inference_time_ms:.2f}ms
- Sentiment Dağılımı: {dict(current.sentiment_distribution)}
- Durum: {current.status.value}
"""
        
        # Önceki metriklerle karşılaştırma
        if previous and previous.total_predictions > 0:
            conf_change = ((current.average_confidence - previous.average_confidence) 
                          / previous.average_confidence * 100)
            latency_change = ((current.average_inference_time_ms - previous.average_inference_time_ms)
                             / previous.average_inference_time_ms * 100)
            
            prompt += f"""
## ÖNCEKİ DÖNEM İLE KARŞILAŞTIRMA
- Güven Skoru Değişimi: {conf_change:+.1f}%
- Gecikme Değişimi: {latency_change:+.1f}%
- Tahmin Sayısı Farkı: {current.total_predictions - previous.total_predictions:+d}
"""
        
        prompt += """
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
        
        return prompt
    
    def _parse_gemini_response(
        self,
        response_text: str,
        metrics: AggregatedMetrics
    ) -> GeminiAnalysisReport:
        """Gemini'nin JSON yanıtını parse et"""
        
        try:
            # JSON'ı çıkar (bazen markdown kod bloğu içinde geliyor)
            json_str = response_text
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            
            # Parse et
            data = json.loads(json_str)
            
            # PerformanceIssue objelerine dönüştür
            issues = [
                PerformanceIssue(**issue)
                for issue in data.get("identified_issues", [])
            ]
            
            # GeminiAnalysisReport oluştur
            return GeminiAnalysisReport(
                summary=data.get("summary", "Analiz tamamlandı"),
                identified_issues=issues,
                recommendations=data.get("recommendations", []),
                root_cause_hypothesis=data.get("root_cause_hypothesis", "Belirsiz"),
                confidence_score=data.get("confidence_score", 0.5),
                metrics_analyzed=metrics
            )
            
        except Exception as e:
            print(f"⚠️ Gemini yanıtı parse edilemedi: {e}")
            print(f"Yanıt: {response_text[:200]}...")
            return self._create_fallback_report(metrics, f"Parse hatası: {str(e)}")
    
    def _create_fallback_report(
        self,
        metrics: AggregatedMetrics,
        error_msg: str
    ) -> GeminiAnalysisReport:
        """Hata durumunda varsayılan rapor oluştur"""
        
        # Basit kural tabanlı analiz
        issues = []
        recommendations = []
        
        if metrics.average_confidence < 0.6:
            issues.append(PerformanceIssue(
                issue_type="low_confidence",
                severity="high",
                description=f"Ortalama güven skoru düşük: {metrics.average_confidence:.2f}"
            ))
            recommendations.append("Model yeniden eğitimi düşünün")
        
        if metrics.average_inference_time_ms > 200:
            issues.append(PerformanceIssue(
                issue_type="high_latency",
                severity="medium",
                description=f"Ortalama gecikme yüksek: {metrics.average_inference_time_ms:.2f}ms"
            ))
            recommendations.append("Sunucu kaynaklarını kontrol edin")
        
        if metrics.total_predictions < 5:
            summary = f"Yetersiz veri: Sadece {metrics.total_predictions} tahmin var. Daha fazla veri toplanmalı."
        else:
            summary = f"Otomatik analiz: {len(issues)} sorun tespit edildi. (Gemini hatası: {error_msg})"
        
        return GeminiAnalysisReport(
            summary=summary,
            identified_issues=issues,
            recommendations=recommendations if recommendations else ["Daha fazla veri toplayın"],
            root_cause_hypothesis="Gemini API kullanılamadığı için kural tabanlı analiz yapıldı",
            confidence_score=0.3,
            metrics_analyzed=metrics
        )


# Global instance
gemini_analyzer = GeminiAnalyzer()
