"""
Gemini API Client

Tenacity retry mantığı ile API iletişimi.
Separation of Concerns: Sadece API çağrısı ve retry yönetimi yapar.
"""
import google.generativeai as genai
from typing import Optional

# Tenacity - Retry mekanizması
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random,
    retry_if_exception_type,
    RetryError
)

# Google API hataları
from google.api_core.exceptions import (
    ServiceUnavailable,      # 503 - Geçici, retry mantıklı
    DeadlineExceeded,        # Timeout - Geçici, retry mantıklı
    InternalServerError,     # 500 - Bazen geçici
    ResourceExhausted,       # 429 - Rate limit (retry YAPMA!)
)

from services.analyzer.config import AnalyzerConfig


class GeminiAPIClient:
    """
    Resilience pattern'leri ile düşük seviye Gemini API istemcisi
    
    Sorumluluklar:
    - API başlatma
    - İstek yürütme
    - Retry yönetimi (Tenacity)
    - Hata sınıflandırma
    
    Retry edilecek hatalar:
    - 503 ServiceUnavailable
    - 500 InternalServerError
    - DeadlineExceeded (Timeout)
    - ConnectionError
    - TimeoutError
    
    Retry EDİLMEYECEK hatalar:
    - 429 ResourceExhausted (Redis rate limit var)
    - 400 InvalidArgument (düzeltilmesi gereken hata)
    - 401/403 Authentication (retry ile düzelmez)
    """
    
    def __init__(self, config: AnalyzerConfig):
        """
        API istemcisini yapılandır
        
        Args:
            config: Analyzer yapılandırması
        """
        self.config = config
        self.model = self._initialize_model()
    
    def _initialize_model(self) -> Optional[genai.GenerativeModel]:
        """
        Gemini modelini yapılandırma ile başlat
        
        Returns:
            GenerativeModel veya None (API key yoksa)
        """
        if not self.config.is_configured:
            print("⚠️  GEMINI_API_KEY bulunamadı! .env dosyasını kontrol edin.")
            print("   API key almak için: https://aistudio.google.com/app/apikey")
            return None
        
        # Gemini yapılandırması
        genai.configure(api_key=self.config.api_key)
        
        # Model instance (Native JSON Mode)
        model = genai.GenerativeModel(
            model_name=self.config.model_name,
            generation_config={
                "temperature": self.config.temperature,
                "max_output_tokens": self.config.max_tokens,
                "response_mime_type": "application/json",  # Native JSON mode
            }
        )
        
        print(f"✅ Gemini API Client hazır")
        print(f"   Model: {self.config.model_name}")
        print(f"   Retry: {self.config.max_retries} deneme (Exponential Backoff)")
        
        return model
    
    @property
    def is_configured(self) -> bool:
        """API key'in geçerli olup olmadığını kontrol et"""
        return self.model is not None
    
    @retry(
        stop=stop_after_attempt(4),  # Maksimum 4 deneme
        wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
        retry=retry_if_exception_type((
            ServiceUnavailable,      # 503 - Geçici
            DeadlineExceeded,        # Timeout - Geçici
            InternalServerError,     # 500 - Bazen geçici
            ConnectionError,         # Network - Geçici
            TimeoutError,            # Python timeout - Geçici
        )),
        # ResourceExhausted (429) burada YOK - Redis rate limit zaten var
        before_sleep=lambda retry_state: print(
            f"⏳ Retry #{retry_state.attempt_number} - "
            f"Bekleniyor: {retry_state.next_action.sleep:.1f}s"
        )
    )
    async def generate(self, prompt: str) -> str:
        """
        Retry koruması ile API çağrısı yap
        
        google-generativeai 0.8.6+ sürümünde generate_content_async()
        native async desteği sağlar. Event loop'u bloklamaz.
        
        Args:
            prompt: Gemini'ye gönderilecek prompt
            
        Returns:
            str: Gemini'den ham yanıt metni
            
        Raises:
            RetryError: Tüm retry denemeleri başarısız
            ResourceExhausted: 429 rate limit (retry yapılmaz)
        """
        if not self.model:
            raise RuntimeError("Gemini model yapılandırılmamış")
        
        # Native async API çağrısı
        response = await self.model.generate_content_async(prompt)
        return response.text


# Re-export exceptions for convenience
__all__ = [
    'GeminiAPIClient',
    'RetryError', 
    'ResourceExhausted'
]
