"""
İstek Şemaları (Request Schemas)
Pydantic modelleri ile gelen verileri doğrulama
"""
from pydantic import BaseModel, Field
from typing import Optional


class PredictRequest(BaseModel):
    """Tahmin isteği için veri modeli"""
    text: str = Field(
        ...,  # ... = zorunlu alan
        min_length=1,
        max_length=1000,
        description="Analiz edilecek metin",
        examples=["Bu ürün gerçekten harika!"]
    )
    
    include_metrics: bool = Field(
        default=True,
        description="Yanıtta metrik bilgisi dönsün mü?"
    )
    
    class Config:
        # Pydantic v2 için JSON schema örnekleri
        json_schema_extra = {
            "example": {
                "text": "Bu ürün gerçekten harika!",
                "include_metrics": True
            }
        }


class MetricsQueryRequest(BaseModel):
    """Metrik sorgulama isteği"""
    time_window_minutes: int = Field(
        default=60,
        ge=1,  # greater than or equal (>=)
        le=1440,  # less than or equal (<=) - Maksimum 24 saat
        description="Kaç dakikalık metrikleri getir?"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "time_window_minutes": 60
            }
        }
