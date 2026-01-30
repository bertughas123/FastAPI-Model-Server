"""
Response Parser

Gemini API yanıtlarını ayrıştırma ve doğrulama.
Separation of Concerns: Sadece JSON parsing yapar.
"""
from schemas.metrics import AggregatedMetrics, GeminiAnalysisReport


class ParseError(Exception):
    """Yanıt ayrıştırma hatası"""
    pass


class ResponseParser:
    """
    Gemini API yanıtlarını ayrıştırır ve doğrular
    
    Sorumluluklar:
    - JSON doğrulama
    - Pydantic model dönüşümü
    - Hatalı yanıtlar için hata yönetimi
    """
    
    def parse(
        self,
        response_text: str,
        metrics: AggregatedMetrics
    ) -> GeminiAnalysisReport:
        """
        Gemini JSON yanıtını Pydantic modeline dönüştür
        
        response_mime_type="application/json" sayesinde Gemini doğrudan
        JSON döner, manuel string parsing'e gerek yok.
        
        Args:
            response_text: API'den gelen ham JSON string
            metrics: Bağlam için orijinal metrikler
            
        Returns:
            GeminiAnalysisReport: Doğrulanmış rapor nesnesi
            
        Raises:
            ParseError: JSON ayrıştırma veya doğrulama başarısız
        """
        try:
            # Pydantic native JSON validation
            report = GeminiAnalysisReport.model_validate_json(response_text)
            
            # Metrik bilgisini manuel olarak ekle (Gemini bunu bilmiyor)
            report.metrics_analyzed = metrics
            
            return report
            
        except Exception as e:
            # Hata detaylarını logla
            print(f"⚠️ Gemini yanıtı parse edilemedi: {e}")
            if response_text:
                print(f"Yanıt: {response_text[:200]}...")
            
            raise ParseError(f"Geçersiz yanıt formatı: {str(e)}")
    
    def try_parse(
        self,
        response_text: str,
        metrics: AggregatedMetrics
    ) -> tuple[GeminiAnalysisReport | None, str | None]:
        """
        Parse işlemini dene, hata durumunda exception fırlatma
        
        Args:
            response_text: API'den gelen ham JSON string
            metrics: Bağlam için orijinal metrikler
            
        Returns:
            tuple: (report, None) başarılı ise, (None, error_msg) başarısız ise
        """
        try:
            report = self.parse(response_text, metrics)
            return report, None
        except ParseError as e:
            return None, str(e)
