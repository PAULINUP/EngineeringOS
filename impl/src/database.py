import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://eos_user:eos_password@localhost:5432/engineeringos")

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
    """Alembic fará as migrações em produção."""
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    pass

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
