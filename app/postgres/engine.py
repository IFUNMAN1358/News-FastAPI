from typing import Generator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import Config


async_engine = create_async_engine(url=Config.postgres_url)

async_session = async_sessionmaker(bind=async_engine,
                                   expire_on_commit=False,
                                   class_=AsyncSession)


async def get_db() -> Generator:
    db = async_session()
    try:
        yield db
    finally:
        await db.close()
