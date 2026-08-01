import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.models import Base

def normalize_db_url(url: str) -> str:
    """
    Plataformas gerenciadas (Railway, Heroku, Fly) entregam a URL no formato
    síncrono — `postgresql://` ou o legado `postgres://`. A aplicação é async e
    precisa do driver asyncpg; sem esta conversão o processo nem sobe.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        url = "sqlite+aiosqlite://" + url[len("sqlite://"):]
    return url


DATABASE_URL = normalize_db_url(
    os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./engineeringos.db")
)

connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args = {"check_same_thread": False, "timeout": 20.0}

engine = create_async_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def init_db() -> None:
    """
    Cria as tabelas automaticamente em todas as execuções.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncSession:
    """Fornece uma sessão assíncrona do banco de dados (Dependency Injection)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
