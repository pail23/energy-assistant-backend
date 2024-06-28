"""Database for Energy Assistant."""

import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from energy_assistant.models.base import Base
from energy_assistant.settings import settings

from .constants import ROOT_LOGGER_NAME

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)

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
    except SQLAlchemyError:
        LOGGER.exception("Error from SQL Alchemy")


AsyncSession = Annotated[async_sessionmaker, Depends(get_session)]
