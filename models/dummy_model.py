"""
Basit bir ML model simülasyonu
Gerçek projede burası scikit-learn, TensorFlow vb. ile doldurulur
"""
import random
import time
from typing import Dict, Any


class DummyMLModel:
    """Eğitimsel amaçlı basit model simülasyonu"""
    
    def __init__(self):
        self.model_name = "DummySentimentAnalyzer"
        self.version = "1.0.0"
        self.is_loaded = False
    
    def load_model(self):
        """Model yükleme simülasyonu"""
        print(f"🔄 {self.model_name} yükleniyor...")
        time.sleep(0.5)  # Yükleme gecikmesi simülasyonu
        self.is_loaded = True
        print(f"✅ {self.model_name} başarıyla yüklendi")
    
    def predict(self, text: str) -> Dict[str, Any]:
        """
        Tahmin yapma simülasyonu
        
        Args:
            text: Analiz edilecek metin
            
        Returns:
            Tahmin sonucu ve güven skoru
        """
        if not self.is_loaded:
            raise RuntimeError("Model henüz yüklenmedi! Önce load_model() çağırın.")
        
        # Basit simülasyon: kelimelere göre sentiment tahmini
        positive_words = ['iyi', 'harika', 'mükemmel', 'güzel', 'süper']
        negative_words = ['kötü', 'berbat', 'fena', 'kötü']
        
        text_lower = text.lower()
        
        # Pozitif/negatif kelime sayıları
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        # Tahmin logiği
        if pos_count > neg_count:
            sentiment = "positive"
            confidence = min(0.6 + (pos_count * 0.1), 0.95)
        elif neg_count > pos_count:
            sentiment = "negative"
            confidence = min(0.6 + (neg_count * 0.1), 0.95)
        else:
            sentiment = "neutral"
            confidence = random.uniform(0.4, 0.6)
        
        # Gecikme simülasyonu (gerçek model inferansı zaman alır)
        inference_time = random.uniform(0.05, 0.15)
        time.sleep(inference_time)
        
        return {
            "sentiment": sentiment,
            "confidence": round(confidence, 2),
            "inference_time_ms": round(inference_time * 1000, 2)
        }


# Global model instance (uygulama başlangıcında yüklenecek)
ml_model = DummyMLModel()
