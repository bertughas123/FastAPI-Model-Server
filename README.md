# 🚀 FastAPI Model Server

ML model serving, performans izleme ve AI-powered analiz için modüler bir FastAPI uygulaması.

## 📋 Özellikler

- **Sentiment Analizi**: Metin tabanlı duygu analizi (positive/negative/neutral)
- **Rate Limiting**: IP tabanlı istek sınırlandırma (10 req/dk)
- **Metrik Toplama**: Tahmin performansını izleme ve raporlama
- **Gemini AI Analizi**: Google Gemini ile akıllı performans analizi
- **Docker Desteği**: PostgreSQL ve PgAdmin container'ları
- **Async Database**: SQLAlchemy + asyncpg ile async PostgreSQL bağlantısı

## 🏗️ Proje Yapısı

```
FastAPI-Model-Server/
├── main.py                     # FastAPI uygulaması (v4.0.0)
├── docker-compose.yml          # PostgreSQL & PgAdmin
├── requirements.txt            # Python bağımlılıkları
├── .env                        # Environment variables
│
├── routes/                     # API Endpoint'leri
│   ├── health.py               # /, /health
│   ├── predict.py              # /predict
│   └── analytics.py            # /metrics/*, /analyze/*
│
├── schemas/                    # Pydantic Modelleri
│   ├── requests.py             # Request şemaları
│   ├── responses.py            # Response şemaları
│   └── metrics.py              # Metrik şemaları
│
├── services/                   # Business Logic
│   ├── metrics_tracker.py      # Metrik toplama (in-memory)
│   ├── metrics_tracker_db.py   # Metrik toplama (PostgreSQL)
│   └── gemini_analyzer.py      # Gemini AI analizi
│
├── database/                   # Veritabanı Katmanı
│   ├── connection.py           # Async SQLAlchemy engine
│   └── models.py               # ORM modelleri
│
├── core/                       # Çekirdek Modüller
│   └── rate_limiter.py         # Rate limiting
│
└── models/                     # ML Modelleri
    └── dummy_model.py          # Simüle sentiment model
```

## 🔧 Kurulum

### 1. Repository'yi Klonla
```bash
git clone https://github.com/your-username/FastAPI-Model-Server.git
cd FastAPI-Model-Server
```

### 2. Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# veya
source .venv/bin/activate  # Linux/Mac
```

### 3. Bağımlılıkları Yükle
```bash
pip install -r requirements.txt
```

### 4. Environment Variables
```bash
cp .env.example .env
# .env dosyasını düzenleyin (API key'ler, DB credentials)
```

### 5. Docker (PostgreSQL & PgAdmin)
```bash
docker-compose up -d
```

### 6. Sunucuyu Başlat
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 🌐 API Endpoints

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/` | Ana sayfa |
| GET | `/health` | Sağlık kontrolü |
| POST | `/predict` | Sentiment tahmini (rate limited) |
| POST | `/metrics/aggregated` | Toplam metrikler |
| PUT | `/metrics/thresholds` | Eşik değerlerini güncelle |
| GET | `/metrics/count` | Metrik sayısı |
| POST | `/analyze/performance` | Gemini AI analizi |

### Örnek İstekler

**Tahmin Yap:**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "Bu ürün harika!"}'
```

**Yanıt:**
```json
{
  "sentiment": "positive",
  "confidence": 0.92,
  "inference_time_ms": 45.2,
  "model_version": "1.0.0"
}
```

**Gemini Analizi:**
```bash
curl -X POST http://localhost:8000/analyze/performance \
  -H "Content-Type: application/json" \
  -d '{"time_window_minutes": 60}'
```

## 📖 Dokümantasyon

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **PgAdmin**: http://localhost:8080

## 🛠️ Teknolojiler

| Teknoloji | Versiyon | Kullanım |
|-----------|----------|----------|
| FastAPI | 0.104.1 | Web framework |
| Pydantic | 2.10.5 | Veri validasyonu |
| SQLAlchemy | 2.0.35 | Async ORM |
| asyncpg | 0.30.0 | PostgreSQL driver |
| PostgreSQL | 16 | Veritabanı |
| Google Generative AI | 0.3.2 | Gemini API |
| Docker | - | Container orchestration |

## 🔐 Environment Variables

| Değişken | Açıklama |
|----------|----------|
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_MODEL` | Gemini model adı |
| `DATABASE_URL` | PostgreSQL async URL |
| `POSTGRES_USER` | DB kullanıcı adı |
| `POSTGRES_PASSWORD` | DB şifresi |
| `POSTGRES_DB` | Veritabanı adı |

## 📄 Lisans

MIT License - Detaylar için [LICENSE](LICENSE) dosyasına bakın.
