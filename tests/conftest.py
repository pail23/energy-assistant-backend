"""Conf test for Energy Assistant."""
from typing import AsyncGenerator, Generator

import pytest
from httpx import AsyncClient
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, SessionTransaction

from app.db import get_session
from app.main import app
from app.models.base import Base
from app.settings import Settings
import contextlib

settings = Settings.parse_obj({})


@pytest.fixture
async def ac() -> AsyncGenerator:
    async with AsyncClient(app=app, base_url="https://test") as c:
        yield c


@pytest.fixture(scope="session")
async def setup_db() -> Generator:
    engine = create_async_engine(settings.DB_URI)
    async with engine.connect() as conn:
        conn.execute(text("commit"))
        try:
            conn.execute(text("drop database test"))
        except SQLAlchemyError:
            pass
        finally:
            conn.close()

    conn = engine.connect()
    conn.execute(text("commit"))
    conn.execute(text("create database test"))
    conn.close()

    yield

    conn = engine.connect()
    conn.execute(text("commit"))
    with contextlib.suppress(SQLAlchemyError):
        conn.execute(text("drop database test"))

    conn.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db(setup_db: Generator) -> Generator:
    engine = create_async_engine(settings.DB_URI)

    async with engine.begin():
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        yield
        Base.metadata.drop_all(engine)


@pytest.fixture
async def session() -> AsyncGenerator:
    # https://github.com/sqlalchemy/sqlalchemy/issues/5811#issuecomment-756269881
    async_engine = create_async_engine(settings.DB_URI)
    async with async_engine.connect() as conn:
        await conn.begin()
        await conn.begin_nested()
        AsyncSessionLocal = async_sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=conn,
            future=True,
        )

        async_session = AsyncSessionLocal()

        @event.listens_for(async_session.sync_session, "after_transaction_end")
        def end_savepoint(session: Session, transaction: SessionTransaction) -> None:
            if conn.closed:
                return
            if not conn.in_nested_transaction():
                if conn.sync_connection:
                    conn.sync_connection.begin_nested()

        def test_get_session() -> Generator:
            with contextlib.suppress(SQLAlchemyError):
                yield AsyncSessionLocal


        app.dependency_overrides[get_session] = test_get_session

        yield async_session
        await async_session.close()
        await conn.rollback()