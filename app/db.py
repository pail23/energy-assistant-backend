"""Database for Energy Assistant."""

import logging
from typing import Annotated, AsyncIterator

from fastapi import Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base
from app.settings import settings

logger = logging.getLogger(__name__)

async_engine = create_async_engine(
    settings.DB_URI,
    pool_pre_ping=True,
    echo=settings.ECHO_SQL,
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
    future=True,
)


async def create_all() -> None:
    """Create all tables in the database."""
    async with async_engine.begin() as conn:
       await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[async_sessionmaker]:
    """Get the session for db transactions."""
    try:
        yield AsyncSessionLocal
    except SQLAlchemyError as e:
        logger.exception(e)


AsyncSession = Annotated[async_sessionmaker, Depends(get_session)]
