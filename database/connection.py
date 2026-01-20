"""
Async PostgreSQL Bağlantı Yönetimi
"""
from sqlalchemy.ext.asyncio import (
    create_async_engine, 
    AsyncSession, 
    async_sessionmaker
)
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════════
# Veritabanı URL'i (Zorunlu - .env'den okunur)
# ═══════════════════════════════════════════════════════════════════
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise EnvironmentError(
        "❌ DATABASE_URL tanımlı değil!\n"
        "   .env dosyasına ekleyin:\n"
        "   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname"
    )

# ═══════════════════════════════════════════════════════════════════
# Async Engine - Connection Pool
# ═══════════════════════════════════════════════════════════════════
engine = create_async_engine(
    DATABASE_URL,
    echo=True,           # SQL logları (geliştirme için)
    pool_size=10,        # Minimum connection
    max_overflow=20,     # Ek connection limiti
    pool_timeout=30,     # Bağlantı bekleme (saniye)
    pool_recycle=3600,   # Connection yenileme (1 saat)
)

# ═══════════════════════════════════════════════════════════════════
# Async Session Factory
# ═══════════════════════════════════════════════════════════════════
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ═══════════════════════════════════════════════════════════════════
# Base - Tüm modeller buradan türer
# ═══════════════════════════════════════════════════════════════════
Base = declarative_base()


# ═══════════════════════════════════════════════════════════════════
# FastAPI Dependency
# ═══════════════════════════════════════════════════════════════════
async def get_db() -> AsyncSession:
    """
    Her request için ayrı session oluşturur.
    
    Kullanım:
        @router.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ═══════════════════════════════════════════════════════════════════
# Tablo Oluşturma Fonksiyonları
# ═══════════════════════════════════════════════════════════════════
async def create_tables():
    """Uygulama başlangıcında tabloları oluştur"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Veritabanı tabloları oluşturuldu")


async def drop_tables():
    """Test/geliştirme için tabloları sil"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("🗑️ Veritabanı tabloları silindi")
