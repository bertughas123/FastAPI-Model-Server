# FastAPI Model Server

A production-grade ML model serving infrastructure built with FastAPI, featuring real-time performance monitoring, AI-powered analytics, and enterprise-level rate limiting.

---

## Architecture

This server implements a modular architecture for ML model deployment with integrated observability and intelligent performance analysis.

### Core Components

**Prediction Engine**
- Asynchronous inference pipeline with sub-100ms latency tracking
- Pydantic-based request/response validation with semantic versioning enforcement
- Configurable confidence thresholds and automatic model health checks

**Metrics Collection System**
- Real-time aggregation of prediction metrics (confidence, latency, sentiment distribution)
- Time-windowed statistical analysis (P95 latency, average confidence, throughput)
- Threshold-based alerting with WARNING/CRITICAL status levels

**AI-Powered Analytics**
- Google Gemini integration for automated performance degradation analysis
- Comparative metric evaluation with root cause hypothesis generation
- Intelligent caching layer (5-minute TTL) to optimize API usage

**Rate Limiting**
- IP-based sliding window rate limiter (10 requests/minute default)
- Automatic timestamp cleanup with deque-based memory efficiency
- HTTP 429 responses with detailed error messaging

---

## Project Structure

```
FastAPI-Model-Server/
├── core/
│   ├── __init__.py
│   └── rate_limiter.py          # IP-based request throttling
├── models/
│   ├── __init__.py
│   └── dummy_model.py            # ML model abstraction layer
├── routes/
│   ├── __init__.py
│   ├── health.py                 # Health check and uptime endpoints
│   ├── predict.py                # Prediction endpoint with rate limiting
│   └── analytics.py              # Metrics and AI analysis endpoints
├── schemas/
│   ├── __init__.py
│   ├── requests.py               # Request validation schemas
│   ├── responses.py              # Response models
│   └── metrics.py                # Metric data structures and enums
├── services/
│   ├── __init__.py
│   ├── metrics_tracker.py        # Metric aggregation service
│   └── gemini_analyzer.py        # AI-powered performance analyzer
├── main.py                       # Application entry point
├── requirements.txt
└── .env.example
```

---

## API Endpoints

### Health & Status

**`GET /`**  
Returns service status and documentation links.

**`GET /health`**  
Provides detailed health metrics including model load status, version, and uptime.

### Predictions

**`POST /predict`**  
Executes sentiment analysis with automatic metric collection.

**Request Schema:**
```json
{
  "text": "string (1-1000 chars)",
  "include_metrics": "boolean (default: true)"
}
```

**Response Schema:**
```json
{
  "sentiment": "positive | negative | neutral",
  "confidence": "float (0.0-1.0)",
  "inference_time_ms": "float",
  "timestamp": "ISO 8601 string",
  "model_version": "string (semantic versioning)",
  "metric": "PredictionMetric (optional)"
}
```

**Rate Limit:** 10 requests/minute per IP  
**Status Codes:** 200 (Success), 429 (Rate Limit), 503 (Model Unavailable), 500 (Inference Error)

### Analytics

**`POST /metrics/aggregated`**  
Retrieves aggregated metrics for a specified time window.

**Request Schema:**
```json
{
  "time_window_minutes": "integer (1-1440)"
}
```

**Response:** Statistical summary including total predictions, average confidence, latency percentiles (min/max/P95), and sentiment distribution.

**`PUT /metrics/thresholds`**  
Updates metric threshold values for WARNING/CRITICAL alerting.

**`GET /metrics/count`**  
Returns total prediction count since server startup.

**`POST /analyze/performance`**  
Triggers AI-powered performance analysis using Google Gemini.

**Response Schema:**
```json
{
  "summary": "string",
  "identified_issues": "PerformanceIssue[]",
  "recommendations": "string[]",
  "root_cause_hypothesis": "string",
  "confidence_score": "float (0.0-1.0)",
  "generated_at": "ISO 8601 string",
  "metrics_analyzed": "AggregatedMetrics"
}
```

---

## Technical Implementation

### Validation Layer

The server enforces strict data validation using Pydantic v2:

- **Semantic Versioning Validation:** Model versions must follow `X.Y.Z` format
- **Enum-based Sentiment Types:** Prevents invalid sentiment values
- **Field Constraints:** Automatic validation of ranges (confidence: 0-1, text length: 1-1000)
- **Custom Validators:** Cross-field validation for threshold consistency

### Performance Monitoring

**Metric Collection:**
- UUID-based prediction tracking
- Automatic timestamp recording (UTC)
- Input length correlation analysis
- Model version tracking for A/B testing support

**Aggregation Engine:**
- Time-windowed filtering with datetime arithmetic
- Statistical computation (mean, min, max, P95)
- Sentiment distribution histograms
- Status determination based on configurable thresholds

### AI Integration

**Gemini Analyzer Features:**
- Dual-period comparative analysis (current vs. previous window)
- Structured JSON response parsing with fallback handling
- Built-in rate limiting (10 requests/minute)
- Cache-first strategy with MD5-based key generation
- Automatic retry logic with exponential backoff

**Prompt Engineering:**
The analyzer uses a specialized prompt template that:
- Provides metric context with statistical summaries
- Requests structured JSON output with specific fields
- Enforces severity classification (low/medium/high/critical)
- Demands actionable recommendations

---

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Google Gemini API Key
# Generate at: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_api_key_here

# Model Configuration
GEMINI_MODEL=gemini-2.5-flash-lite
GEMINI_TEMPERATURE=0.3
GEMINI_MAX_TOKENS=1024
```

### Threshold Configuration

Default metric thresholds (modifiable via `/metrics/thresholds`):

| Metric | Warning | Critical |
|--------|---------|----------|
| Min Confidence | 0.6 | 0.4 |
| Max Inference Time | 200ms | 500ms |

---

## Installation

### Prerequisites

- Python 3.10+
- Google Gemini API key

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd FastAPI-Model-Server

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### Running the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Access Points:**
- API: `http://localhost:8000`
- Interactive Documentation: `http://localhost:8000/docs`
- Alternative Documentation: `http://localhost:8000/redoc`

---

## Dependencies

```
fastapi==0.104.1          # Async web framework
uvicorn[standard]==0.24.0 # ASGI server with WebSocket support
pydantic==2.10.5          # Data validation and settings management
python-dotenv==1.0.0      # Environment variable management
google-generativeai==0.3.2 # Google Gemini API client
```

---

## Development Roadmap

### Planned Enhancements

**Database Migration**  
Transition from in-memory storage to PostgreSQL with Docker containerization:
- Persistent metric storage with time-series optimization
- Multi-instance deployment support with shared state
- ACID-compliant transactions for data integrity
- Foreign key relationships for model versioning

**Advanced Features**
- Alembic-based schema migrations
- Redis caching layer for Gemini responses
- PgAdmin integration for database management
- Horizontal scaling with connection pooling

See `POSTGRESQL_MIGRATION_PLAN.md` for detailed implementation strategy.

---

## Testing

The project includes comprehensive test suites:

- `test_stage2.py` - Schema validation and metrics tracking tests
- `test_stage3.py` - Gemini integration and analytics tests
- `test_rate_limit.py` - Rate limiting behavior verification

```bash
# Run all tests
pytest -v

# Run specific test file
pytest test_stage3.py -v
```

---

## Error Handling

The server implements comprehensive error handling:

| Status Code | Scenario | Response |
|-------------|----------|----------|
| 200 | Successful prediction | PredictResponse with metrics |
| 404 | Invalid endpoint | Available endpoints list |
| 429 | Rate limit exceeded | Retry-after information |
| 500 | Inference failure | Detailed error message |
| 503 | Model not loaded | Service unavailable notice |

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

Copyright (c) 2026 Bertuğ Has

---

## Documentation

For detailed implementation guides and migration strategies, refer to:

- `POSTGRESQL_MIGRATION_PLAN.md` - Database migration strategy
- `POSTGRESQL_MIGRATION_WALKTHROUGH.md` - Step-by-step migration guide
- `RATE_LIMITING_DOKUMAN.md` - Rate limiting implementation details
- Stage-specific guides: `ASAMA_*.md` files for incremental development phases
