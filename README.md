# FastAPI Model Server - Öğrenme Projesi 🚀

## 📖 Proje Hakkında

Bu proje, **FastAPI** kullanarak **Machine Learning model serving** yapan, performans metriklerini toplayan ve **Gemini AI** ile analiz eden production-ready bir backend sistemidir.

## 🎯 Öğrenme Hedefleri

4 aşamalı müfredat ile şunları öğreneceksiniz:

1. **Aşama 1:** FastAPI temelleri ve asenkron programlama → [ASAMA_1_TEMEL_API.md](ASAMA_1_TEMEL_API.md)
2. **Aşama 2:** Pydantic ile veri doğrulama ve metrik sistemi → [ASAMA_2_SEMA_DOGRULAMA.md](ASAMA_2_SEMA_DOGRULAMA.md)
3. **Aşama 3:** Gemini API ile akıllı performans analizi → [ASAMA_3_GEMINI_ANALIZ.md](ASAMA_3_GEMINI_ANALIZ.md)
4. **Aşama 4:** REST API tasarımı ve frontend entegrasyonu → [ASAMA_4_MONITORING_RAPORLAMA.md](ASAMA_4_MONITORING_RAPORLAMA.md)

## 🏗️ Proje Yapısı

```
FastAPI-Model-Server/
├── main.py                    # Ana uygulama dosyası
├── models/
│   └── dummy_model.py         # ML model simülasyonu
├── schemas/
│   ├── requests.py            # İstek şemaları (Pydantic)
│   ├── responses.py           # Yanıt şemaları
│   └── metrics.py             # Metrik veri yapıları
├── services/
│   ├── metrics_tracker.py     # Metrik toplama servisi
│   ├── gemini_analyzer.py     # Gemini AI analiz servisi
│   └── report_generator.py    # Raporlama servisi
├── middleware/
│   └── cors.py                # CORS konfigürasyonu
├── .env                       # Ortam değişkenleri (API keys)
├── .env.example              # .env şablonu
├── requirements.txt          # Python bağımlılıkları
├── README.md                 # Bu dosya
└── ASAMA_*.md               # Müfredat dokümanları
```

## 🚀 Hızlı Başlangıç

### 1. Gereksinimler
- Python 3.9+
- pip (Python paket yöneticisi)

### 2. Kurulum

```bash
# Sanal ortam oluştur ve aktive et
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Bağımlılıkları yükle
pip install -r requirements.txt
```

### 3. Gemini API Key Ayarla (Aşama 3 için)

1. https://aistudio.google.com/app/apikey adresinden API key alın
2. `.env.example` dosyasını `.env` olarak kopyalayın
3. API key'inizi `.env` dosyasına ekleyin:
   ```bash
   GEMINI_API_KEY=your_actual_api_key_here
   ```

### 4. Sunucuyu Başlat

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. API'yi Test Et

- **Swagger UI:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc

**cURL Örneği:**
```bash
# Tahmin yap
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "Bu ürün gerçekten harika!"}'

# Dashboard verisi
curl http://localhost:8000/api/v1/dashboard?time_window_minutes=60 | jq
```

## 📚 Öğrenme Yolu

### Başlangıç: Aşama 1
[ASAMA_1_TEMEL_API.md](ASAMA_1_TEMEL_API.md) dosyasını açın ve:
1. Teori bölümünü okuyun
2. Kod örneklerini çalıştırın
3. Challenge görevlerini tamamlayın
4. Bir sonraki aşamaya geçin

**Her aşamada:**
- ✅ Önce teoriyi anlayın
- ✅ Kodu çalıştırıp test edin
- ✅ En az 2 challenge'ı tamamlayın
- ✅ Kendi başınıza kod yazın

## 🛠️ Teknoloji Stack

| Katman | Teknoloji | Neden? |
|--------|-----------|--------|
| Framework | FastAPI | Hızlı, async, otomatik dokümantasyon |
| Validation | Pydantic | Tip güvenliği, otomatik doğrulama |
| AI | Gemini 1.5 Flash | Hızlı, uygun maliyetli LLM |
| Runtime | Uvicorn | ASGI server, yüksek performans |

## 📊 API Endpoint'leri

### Core Endpoints
- `GET /` - Ana sayfa
- `GET /api/v1/health` - Sağlık kontrolü
- `POST /api/v1/predict` - Model tahmini
- `GET /api/v1/dashboard` - Dashboard verisi (Frontend için)

### Analysis Endpoints
- `POST /analyze/performance` - Gemini AI analizi
- `GET /api/v1/reports/daily` - Günlük rapor
- `GET /api/v1/reports/timeseries` - Zaman serisi verileri

## 🎓 Challenge Görevleri

Her aşamada 3 zorluk seviyesinde görevler var:
- 🟢 **Kolay:** Temel kavramları pekiştirme
- 🟡 **Orta:** Gerçek dünya problemleri
- 🔴 **Zor:** İleri seviye özellikler

**Örnek Görevler:**
- Yeni endpoint'ler ekleyin
- Custom validator'lar yazın
- Gemini prompt'larını optimize edin
- React dashboard entegrasyonu yapın

## 🐛 Sorun Giderme

### Model yüklenmiyor
```bash
# Terminal'de şu satırı görüyor musunuz?
# ✅ DummySentimentAnalyzer başarıyla yüklendi
```

### Gemini API hatası
```bash
# .env dosyasını kontrol edin
cat .env  # Linux/Mac
type .env  # Windows

# API key'in geçerli olduğundan emin olun
```

### CORS hatası (Frontend'den istek atarken)
- `middleware/cors.py` dosyasında frontend URL'inizi kontrol edin
- Tarayıcı console'unda detaylı hata mesajını inceleyin

## 📖 Ek Kaynaklar

- [FastAPI Resmi Dokümantasyon](https://fastapi.tiangolo.com/)
- [Pydantic Dokümantasyon](https://docs.pydantic.dev/)
- [Gemini API Dokümantasyon](https://ai.google.dev/docs)
- [Python Async/Await Rehberi](https://realpython.com/async-io-python/)

## 🤝 Katkıda Bulunma

Bu bir öğrenme projesidir. Kendi branch'inizi oluşturup deneyler yapabilirsiniz:

```bash
git checkout -b feature/benim-deneyim
# Değişikliklerinizi yapın
git commit -m "Yeni özellik: X"
```

## 📝 Lisans

Bu proje eğitim amaçlıdır ve özgürce kullanılabilir.

## 🎉 Başarı Kriterleri

Bu müfredatı tamamladığınızda:

✅ FastAPI ile RESTful API geliştirebileceksiniz  
✅ Pydantic ile güvenli veri doğrulama yapabileceksiniz  
✅ LLM API'lerini entegre edebileceksiniz  
✅ Production-ready backend sistemleri tasarlayabileceksiniz  
✅ Frontend ile sorunsuz entegrasyon yapabileceksiniz

**Haydi başlayalım!** 🚀 [Aşama 1'e git →](ASAMA_1_TEMEL_API.md)
