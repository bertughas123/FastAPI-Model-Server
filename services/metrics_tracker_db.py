"""
Async PostgreSQL Tabanlı Metrik Tracker
Dict/List yapısından veritabanına dönüşüm
"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import PredictionMetricDB, ModelVersionDB, SentimentTypeDB, MetricThresholdsDB
from schemas.metrics import AggregatedMetrics, MetricStatus, SentimentType
from datetime import datetime, timedelta
import uuid


class MetricsTrackerDB:
    """Session-based async metrik tracker"""
    
    def __init__(self, session: AsyncSession):
        """
        Args:
            session: FastAPI Depends ile inject edilen AsyncSession
        """
        self.session = session
    
    async def add_metric(
        self,
        sentiment: str,
        confidence: float,
        inference_time_ms: float,
        input_length: int,
        model_version: str
    ) -> PredictionMetricDB:
        """
        Yeni tahmin metriği ekle
        
        Eski: self.metrics.append(metric)
        Yeni: session.add(metric) + flush
        """
        # Model versiyonunu bul veya oluştur
        model_db = await self._get_or_create_model_version(model_version)
        
        # Sentiment enum dönüşümü
        sentiment_enum = SentimentTypeDB(sentiment)
        
        # Metrik objesi oluştur
        db_metric = PredictionMetricDB(
            prediction_id=str(uuid.uuid4()),
            sentiment=sentiment_enum,
            confidence=confidence,
            inference_time_ms=inference_time_ms,
            input_length=input_length,
            timestamp=datetime.utcnow(),
            model_version_id=model_db.id if model_db else None
        )
        
        # Veritabanına ekle
        self.session.add(db_metric)
        await self.session.flush()
        
        return db_metric
    
    async def get_aggregated_metrics(
        self,
        time_window_minutes: int = 60
    ) -> AggregatedMetrics:
        """
        Belirli zaman aralığı için toplam metrikleri hesapla
        
        Eski: [m for m in self.metrics if m.timestamp >= window_start]
        Yeni: SELECT ... WHERE timestamp >= :window_start
        """
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=time_window_minutes)
        
        # Aggregate sorgusu (P95 dahil)
        stmt = select(
            func.count(PredictionMetricDB.id).label("total"),
            func.avg(PredictionMetricDB.confidence).label("avg_conf"),
            func.avg(PredictionMetricDB.inference_time_ms).label("avg_time"),
            func.min(PredictionMetricDB.inference_time_ms).label("min_time"),
            func.max(PredictionMetricDB.inference_time_ms).label("max_time"),
            func.percentile_cont(0.95).within_group(
                PredictionMetricDB.inference_time_ms
            ).label("p95_time"),
        ).where(
            PredictionMetricDB.timestamp >= window_start
        )
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        # Boş sonuç kontrolü
        if not row or row.total == 0:
            return self._empty_aggregated_metrics(window_start, now)
        
        # Sentiment dağılımı
        sentiment_dist = await self._get_sentiment_distribution(window_start)
        
        # Threshold'ları al ve status belirle
        thresholds = await self.get_thresholds()
        status = self._determine_status(
            row.avg_conf or 0.0,
            row.avg_time or 0.0,
            thresholds
        )
        
        return AggregatedMetrics(
            total_predictions=row.total or 0,
            average_confidence=round(row.avg_conf or 0.0, 2),
            average_inference_time_ms=round(row.avg_time or 0.0, 2),
            min_inference_time_ms=round(row.min_time or 0.0, 2),
            max_inference_time_ms=round(row.max_time or 0.0, 2),
            p95_inference_time_ms=round(row.p95_time, 2) if row.p95_time else None,
            sentiment_distribution=sentiment_dist,
            status=status,
            time_window_start=window_start,
            time_window_end=now
        )
    
    async def _get_or_create_model_version(self, version: str) -> ModelVersionDB:
        """Model versiyonunu bul veya oluştur"""
        stmt = select(ModelVersionDB).where(ModelVersionDB.version == version)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if not model:
            model = ModelVersionDB(version=version)
            self.session.add(model)
            await self.session.flush()
        
        return model
    
    async def _get_sentiment_distribution(self, window_start: datetime) -> dict:
        """Sentiment dağılımını hesapla"""
        stmt = select(
            PredictionMetricDB.sentiment,
            func.count(PredictionMetricDB.id).label("count")
        ).where(
            PredictionMetricDB.timestamp >= window_start
        ).group_by(PredictionMetricDB.sentiment)
        
        result = await self.session.execute(stmt)
        
        dist = {
            SentimentType.POSITIVE: 0,
            SentimentType.NEGATIVE: 0,
            SentimentType.NEUTRAL: 0
        }
        
        for row in result:
            # DB enum -> Pydantic enum dönüşümü
            pydantic_sentiment = SentimentType(row.sentiment.value)
            dist[pydantic_sentiment] = row.count
        
        return dist
    
    # ════════════════════════════════════════════════════════════════════
    # THRESHOLD YÖNETİMİ (Aşama 4B)
    # ════════════════════════════════════════════════════════════════════
    
    async def get_thresholds(self, profile_name: str = "default") -> MetricThresholdsDB:
        """Eşik değerlerini veritabanından al"""
        stmt = select(MetricThresholdsDB).where(
            MetricThresholdsDB.name == profile_name
        )
        result = await self.session.execute(stmt)
        thresholds = result.scalar_one_or_none()
        
        if not thresholds:
            # Varsayılan değerlerle oluştur
            thresholds = MetricThresholdsDB(name=profile_name)
            self.session.add(thresholds)
            await self.session.flush() # to prevent the connection from closing :)
        
        return thresholds
    
    async def update_thresholds(
        self, 
        new_thresholds: dict,
        profile_name: str = "default"
    ) -> MetricThresholdsDB:
        """Eşik değerlerini güncelle"""
        thresholds = await self.get_thresholds(profile_name)
        
        for key, value in new_thresholds.items():
            if hasattr(thresholds, key):
                setattr(thresholds, key, value)
        
        thresholds.updated_at = datetime.utcnow()
        await self.session.flush()
        
        return thresholds
    
    def _determine_status(
        self,
        avg_confidence: float,
        avg_inference_time: float,
        thresholds: MetricThresholdsDB
    ) -> MetricStatus:
        """Metrik durumunu belirle"""
        if (avg_confidence <= thresholds.min_confidence_critical or
            avg_inference_time >= thresholds.max_inference_time_critical_ms):
            return MetricStatus.CRITICAL
        
        if (avg_confidence <= thresholds.min_confidence_warning or
            avg_inference_time >= thresholds.max_inference_time_warning_ms):
            return MetricStatus.WARNING
        
        return MetricStatus.NORMAL
    
    def _empty_aggregated_metrics(
        self, 
        window_start: datetime, 
        window_end: datetime
    ) -> AggregatedMetrics:
        """Boş metrik seti döndür"""
        return AggregatedMetrics(
            total_predictions=0,
            average_confidence=0.0,
            average_inference_time_ms=0.0,
            min_inference_time_ms=0.0,
            max_inference_time_ms=0.0,
            p95_inference_time_ms=None,
            sentiment_distribution={
                SentimentType.POSITIVE: 0,
                SentimentType.NEGATIVE: 0,
                SentimentType.NEUTRAL: 0
            },
            status=MetricStatus.NORMAL,
            time_window_start=window_start,
            time_window_end=window_end
        )
