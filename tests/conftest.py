"""Conf test for Energy Assistant."""

import contextlib
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, SessionTransaction

from energy_assistant.db import get_session
from energy_assistant.devices.config import EnergyAssistantConfig
from energy_assistant.devices.home import Home
from energy_assistant.devices.registry import DeviceTypeRegistry
from energy_assistant.main import EnergyAssistant, app
from energy_assistant.models.base import Base
from energy_assistant.settings import settings
from energy_assistant.storage.config import ConfigStorage
from energy_assistant.storage.storage import session_storage


@pytest.fixture()
async def ac() -> AsyncGenerator:
    """Test fixture for a client connection to the backend."""
    config = ConfigStorage(Path(settings.DATA_FOLDER))
    config_file = Path(__file__).parent / "config.yaml"
    await config.initialize(config_file)
    result = EnergyAssistant()
    result.config = EnergyAssistantConfig(config, {})
    home_config = config.home
    if home_config is not None and home_config.get("name") is not None:
        home = Home(config, session_storage, DeviceTypeRegistry())
        result.home = home
    app.energy_assistant = result  # type: ignore

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def setup_test_db() -> Generator:
    """Set up the test database."""
    engine = create_engine(f"{settings.DB_URI.replace('+aiosqlite', '')}")

    with engine.begin():
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        yield
        Base.metadata.drop_all(engine)


@pytest.fixture()
async def session() -> AsyncGenerator:
    """Test fixure for a session."""
    # https://github.com/sqlalchemy/sqlalchemy/issues/5811#issuecomment-756269881
    async_engine = create_async_engine(settings.DB_URI)
    async with async_engine.connect() as conn:
        await conn.begin()
        await conn.begin_nested()
        async_session_local = async_sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=conn,
            future=True,
        )

        async_session = async_session_local()

        @event.listens_for(async_session.sync_session, "after_transaction_end")
        def end_savepoint(session: Session, transaction: SessionTransaction) -> None:
            if conn.closed:
                return
            if not conn.in_nested_transaction() and conn.sync_connection:
                conn.sync_connection.begin_nested()

        def test_get_session() -> Generator:
            with contextlib.suppress(SQLAlchemyError):
                yield async_session_local

        app.dependency_overrides[get_session] = test_get_session

        yield async_session
        await async_session.close()
        await conn.rollback()


@pytest.fixture()
def device_type_registry() -> DeviceTypeRegistry:
    """Device Type Registry test fixture."""
    return DeviceTypeRegistry()
