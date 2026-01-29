# FastAPI Model Server

Production-ready ML model serving platform with distributed caching, rate limiting, and AI-powered performance analytics.

---

## Technology Stack

### Core Framework
| Technology | Version | Purpose |
|------------|---------|---------|
| **FastAPI** | 0.104.1 | Async web framework with automatic OpenAPI documentation |
| **Pydantic v2** | 2.10.5 | Data validation, serialization, and schema generation |
| **Uvicorn** | - | ASGI server with production-ready performance |

### Database Layer
| Technology | Version | Purpose |
|------------|---------|---------|
| **PostgreSQL** | 16 | Primary data store for metrics and predictions |
| **SQLAlchemy 2.0** | 2.0.35 | Async ORM with native asyncio support |
| **asyncpg** | 0.30.0 | High-performance async PostgreSQL driver |
| **Alembic** | - | Database migrations |

### Caching & Rate Limiting
| Technology | Version | Purpose |
|------------|---------|---------|
| **Redis** | 5.0.1 | Distributed cache and rate limiter backend |
| **redis-py (asyncio)** | - | Async Redis client with connection pooling |
| **hiredis** | - | C-based parser for improved Redis performance |

### AI/ML Integration
| Technology | Version | Purpose |
|------------|---------|---------|
| **Google Generative AI** | 0.8.6 | Gemini API for performance analysis |
| **Tenacity** | 8.2.3 | Retry mechanism with exponential backoff |

### DevOps & Infrastructure
| Technology | Purpose |
|------------|---------|
| **Docker** | Containerization |
| **Docker Compose** | Multi-container orchestration |
| **PgAdmin** | Database administration UI |

---

## Architecture Overview

```
                                    FastAPI Application
                                           |
                    +----------------------+----------------------+
                    |                      |                      |
              [Rate Limiter]         [ML Service]          [Analytics]
                    |                      |                      |
            +-------+-------+              |              +-------+-------+
            |               |              |              |               |
      [PostgreSQL]      [Redis]      [Prediction]    [Gemini API]   [Redis Cache]
      (Ingress RPS)   (API Quota)      Engine      (AI Analysis)   (Report Cache)
```

### Key Architectural Patterns

**1. Dual-Layer Rate Limiting**
- Ingress Layer (PostgreSQL): Request-per-second limiting per IP
- Egress Layer (Redis): Global API quota management with sliding window

**2. Cache-First Pattern with Distributed Locking**
- Redis-based caching with TTL management
- Double-Checked Locking to prevent Cache Stampede
- 50 concurrent requests result in only 1 API call

**3. Resilience Patterns**
- Exponential backoff with jitter (Tenacity)
- Automatic retry on transient failures (503, 500, timeout)
- Fallback reports when API is unavailable


## API Endpoints

| Method | Endpoint | Description | Rate Limited |
|--------|----------|-------------|--------------|
| GET | `/` | Application info | No |
| GET | `/health` | Health check with DB status | No |
| POST | `/predict` | Sentiment prediction | Yes (IP-based) |
| POST | `/metrics/aggregated` | Aggregated performance metrics | No |
| PUT | `/metrics/thresholds` | Update alert thresholds | No |
| GET | `/metrics/count` | Total prediction count | No |
| POST | `/analyze/performance` | AI-powered performance analysis | Yes (Global) |

---

## Key Features

### Distributed Caching
- SHA256-based deterministic cache keys
- Automatic JSON serialization for Pydantic models
- SCAN-based cache invalidation (non-blocking)
- Lazy initialization for Redis services

### Rate Limiting Architecture
```
Request --> [PostgreSQL Ingress] --> [Redis Egress] --> [API Call]
               (60 req/min/IP)        (10 req/min)
```

### Cache Stampede Prevention
```
50 requests --> Cache MISS --> Lock acquired --> 1 API call --> Cache SET
                               |
                               +-- 49 requests wait
                               +-- Double-check cache
                               +-- Return cached result
```

### Retry Strategy
| Attempt | Wait Time | Cumulative |
|---------|-----------|------------|
| 1 | Immediate | 0s |
| 2 | 1-2s | 1-2s |
| 3 | 2-4s | 3-6s |
| 4 | 4-8s | 7-14s |
| Fallback | - | Rule-based report |

---

## Installation

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- PostgreSQL 16 (via Docker)
- Redis 7+ (via Docker)

### Setup

```bash
# Clone repository
git clone https://github.com/your-username/FastAPI-Model-Server.git
cd FastAPI-Model-Server

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and database credentials

# Start infrastructure
docker-compose up -d

# Run application
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL async connection string | - |
| `REDIS_HOST` | Redis server hostname | localhost |
| `REDIS_PORT` | Redis server port | 6379 |
| `REDIS_DB` | Redis database index | 0 |
| `GEMINI_API_KEY` | Google Generative AI API key | - |
| `GEMINI_MODEL` | Gemini model name | gemini-2.5-flash-lite |
| `GEMINI_RATE_LIMIT` | API calls per minute | 10 |
| `GEMINI_CACHE_TTL` | Cache TTL in seconds | 300 |

---

## Documentation

- **OpenAPI (Swagger)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **PgAdmin**: http://localhost:8080

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Concurrent connections | 1000+ (async) |
| Average response time | <50ms (cached) |
| Cache hit ratio | >90% (typical) |
| API cost reduction | 50x (with locking) |

---

## License

MIT License - See [LICENSE](LICENSE) for details.
