from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from app.core.config import settings
from app.models.base import Base

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

# Async session maker
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    """Dependency for getting DB sessions in routes."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Initialize database tables."""
    # Ensure models are imported for metadata mapping
    from app.models.call import Call, CallEvent
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def check_db_health() -> bool:
    """Check database health by running a simple query."""
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False
