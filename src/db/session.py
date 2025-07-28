from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from settings import config

engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async_session_maker = AsyncSessionLocal


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session