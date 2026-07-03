import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./engineeringos.db")

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 20.0} if "sqlite" in DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def init_db() -> None:
    """Cria todas as tabelas do banco de dados no startup."""
    async with engine.begin() as conn:
        # Cria todas as tabelas registradas no meta-modelo
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
