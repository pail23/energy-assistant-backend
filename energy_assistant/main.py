"""Main module for the energy assistant application."""

import asyncio
import json
import logging
import os
import sys
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, tzinfo
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final

import alembic.config
import pandas as pd
from anyio import open_file
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from colorlog import ColoredFormatter
from energy_assistant_frontend import where as locate_frontend
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from energy_assistant.api.main import router as api_router
from energy_assistant.devices import StatesMultipleRepositories, StatesRepository
from energy_assistant.devices.config import EnergyAssistantConfig
from energy_assistant.devices.evcc import EvccDevice
from energy_assistant.devices.home import Home
from energy_assistant.devices.homeassistant import Homeassistant
from energy_assistant.devices.registry import DeviceTypeRegistry
from energy_assistant.emhass_optimizer import EmhassOptimizer
from energy_assistant.importer.homeassistant import import_data
from energy_assistant.mqtt import MqttConnection
from energy_assistant.settings import settings
from energy_assistant.storage.config import ConfigStorage
from energy_assistant.storage.storage import Database, get_async_session, session_storage
from energy_assistant.websocket import get_home_message, ws_manager, ws_router

from .constants import ROOT_LOGGER_NAME

FORMAT_DATE: Final = "%Y-%m-%d"
FORMAT_TIME: Final = "%H:%M:%S"
FORMAT_DATETIME: Final = f"{FORMAT_DATE} {FORMAT_TIME}"
MAX_LOG_FILESIZE = 1000000 * 10  # 10 MB


class EnergyAssistant:
    """Energy Assistant Application."""

    home: Home
    hass: Homeassistant | None
    optimizer: EmhassOptimizer
    mqtt: MqttConnection | None
    db: Database
    config: EnergyAssistantConfig
    should_stop = False


async def import_data_task(
    home: Home,
    hass: Homeassistant,
    async_session: async_sessionmaker,
    freq: pd.Timedelta,
    days_to_retrieve: int,
) -> None:
    """Import data from home assistant."""
    async with async_session() as session:
        await import_data(home, hass, session, freq, days_to_retrieve)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator:
    """Manage the startup and showdown."""
    ea = await init_app()
    app.energy_assistant = ea  # type: ignore
    bt = asyncio.create_task(background_task(ea))
    optimizer_task = asyncio.create_task(optimize(ea.optimizer))
    importer_task = None
    if ea.hass is not None:
        importer_task = asyncio.create_task(
            import_data_task(ea.home, ea.hass, await get_async_session(), pd.Timedelta(24, "h"), 8),
        )
    scheduler = AsyncIOScheduler()
    scheduler.add_job(async_daily_optimize, trigger="cron", args=[ea], hour="3", minute="0")  # time is UTC
    scheduler.start()
    yield
    ea.should_stop = True
    await optimizer_task
    if importer_task is not None:
        await importer_task
    await bt
    scheduler.shutdown()
    if ea.hass:
        await ea.hass.disconnect()
    print("Shutdown app")


app = FastAPI(title="energy-assistant", lifespan=lifespan)


origins = [
    "http://localhost",
    "http://localhost:5000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(ws_router)


async def async_handle_state_update(
    ea: EnergyAssistant,
    state_repository: StatesRepository,
    session: AsyncSession,
    time_zone: tzinfo,
) -> None:
    """Read the values from home assistant and process the update."""
    try:
        await state_repository.async_read_states()

        await ea.home.update_state(state_repository)
        if ea.optimizer is not None:
            await ea.home.update_power_consumption(state_repository, ea.optimizer)
            ea.optimizer.update_repository_states(ea.home, state_repository)
        else:
            logging.error("The variable optimizer is None in async_handle_state_update")
        await state_repository.async_write_states()
        if ea.db:
            if ea.home:
                await asyncio.gather(
                    ws_manager.broadcast(get_home_message(ea.home)),
                    ea.db.store_home_state(ea.home, session, time_zone),
                )
            else:
                logging.error("The variable home is None in async_handle_state_update")
        else:
            logging.error("The variable db is None in async_handle_state_update")
        if ea.optimizer is not None and ea.home is not None:
            await ea.optimizer.async_update_devices(ea.home)
    except Exception:
        logging.exception("error during sending refresh")


async def background_task(ea: EnergyAssistant) -> None:
    """Periodically read the values from home assistant and process the update."""
    time_zone = await ea.hass.get_timezone() if ea.hass is not None else UTC
    last_update = datetime.now(tz=time_zone).date()
    async_session = await get_async_session()
    repositories: list[StatesRepository] = []
    if ea.hass is not None:
        repositories.append(ea.hass)
    if ea.mqtt is not None:
        repositories.append(ea.mqtt)
    state_repository = StatesMultipleRepositories(repositories)
    while not ea.should_stop:
        # delta_t = datetime.now().timestamp()
        # print("Start refresh from home assistant")
        today = datetime.now(tz=time_zone).date()
        try:
            if today != last_update:
                ea.home.store_energy_snapshot()
            last_update = today

            async with async_session() as session:
                await async_handle_state_update(ea, state_repository, session, time_zone)
        except Exception:
            logging.exception("error in the background task")
        # print(f"refresh from home assistant completed in {datetime.now().timestamp() - delta_t} s")
        await asyncio.sleep(30)


def create_mqtt_connection(config: ConfigStorage) -> MqttConnection | None:
    """Create an mqtt connection based on the config."""

    mqtt_config = config.mqtt
    if mqtt_config is not None:
        mqtt_host = mqtt_config.get("host")
        mqtt_username = mqtt_config.get("username")
        mqtt_password = mqtt_config.get("password")
        mqtt_topic = mqtt_config.get("topic")
        mqtt_connection = MqttConnection(mqtt_host, mqtt_username, mqtt_password, mqtt_topic)
        mqtt_connection.connect()
        return mqtt_connection
    return None


def subscribe_mqtt_topics(mqtt_connection: MqttConnection, home: Home) -> None:
    """Subscribe the mqtt based devices on the mqtt connection."""

    for device in home.devices:
        if isinstance(device, EvccDevice):
            mqtt_connection.add_subscription_topic(device.evcc_mqtt_subscription_topic)


async def open_hass_connection(config: ConfigStorage) -> Homeassistant | None:
    """Create a connection to home assistant."""
    token: str | None = None
    url: str | None = None
    try:
        token = os.getenv("SUPERVISOR_TOKEN")
        if token is not None:
            logging.info(f"suvervisor token detected. len={len(token)}")
            url = "http://supervisor/core"

            hass = Homeassistant(url, token, False)
            await hass.connect()
            return hass
    except Exception:
        logging.exception("Error while trying to connect to the homeassistant supervisor api")
        url = None
        token = None

    logging.info("Try to connect to home assistant based on the config file entries...")
    hass_config = config.homeassistant
    if hass_config is not None:
        demo_mode = hass_config.get("demo_mode")
        url = hass_config.get("url")
        token = hass_config.get("token")
        if url is not None and token is not None:
            hass = Homeassistant(url, token, demo_mode)
            await hass.connect()
            return hass
    return None


def setup_logger(log_filename: str, level: str = "DEBUG") -> logging.Logger:
    """Initialize logger."""
    # define log formatter
    log_fmt = "%(asctime)s.%(msecs)03d %(levelname)s (%(threadName)s) [%(name)s] %(message)s"

    # base logging config for the root logger
    logging.basicConfig(level=logging.INFO)

    colorfmt = f"%(log_color)s{log_fmt}%(reset)s"
    logging.getLogger().handlers[0].setFormatter(
        ColoredFormatter(
            colorfmt,
            datefmt=FORMAT_DATETIME,
            reset=True,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red",
            },
        ),
    )

    # Capture warnings.warn(...) and friends messages in logs.
    # The standard destination for them is stderr, which may end up unnoticed.
    # This way they're where other messages are, and can be filtered as usual.
    logging.captureWarnings(True)

    # setup file handler
    # log_filename = os.path.join(data_path, "energy_assistant.log")
    file_handler = RotatingFileHandler(log_filename, maxBytes=MAX_LOG_FILESIZE, backupCount=1)
    # rotate log at each start
    with suppress(OSError):
        file_handler.doRollover()
    file_handler.setFormatter(logging.Formatter(log_fmt, datefmt=FORMAT_DATETIME))
    # file_handler.setLevel(logging.INFO)

    logger = logging.getLogger()
    logger.addHandler(file_handler)

    # apply the configured global log level to the (root) music assistant logger
    logging.getLogger(ROOT_LOGGER_NAME).setLevel(level)

    # silence some noisy loggers
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("databases").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    sys.excepthook = lambda *args: logging.getLogger(None).exception(
        "Uncaught exception",
        exc_info=args,  # type: ignore[arg-type]
    )
    threading.excepthook = lambda args: logging.getLogger(None).exception(
        "Uncaught thread exception",
        exc_info=(  # type: ignore[arg-type]
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
        ),
    )

    return logger


async def init_app() -> EnergyAssistant:
    """Initialize the application."""
    result = EnergyAssistant()

    hass_options_file = Path("/data/options.json")
    if hass_options_file.is_file():
        async with await open_file(hass_options_file) as _file:
            hass_options = json.loads(await _file.read())
    else:
        hass_options = {}

    log_level = hass_options.get("log_level", "info").upper()

    logger = setup_logger(settings.LOG_FILE, log_level)

    config_file = hass_options.get("config_file", settings.CONFIG_FILE)

    logger.info("Hello from Energy Assistant")

    for option in hass_options:
        logging.info(f"{option}={hass_options[option]}")

    async_session = await get_async_session()
    db = Database()
    result.db = db

    device_registry_path = Path(__file__).parent / "config/deviceregistry"

    device_type_registry = DeviceTypeRegistry()
    device_type_registry.load(device_registry_path)

    logger.info(f"Loading config file {config_file}")
    try:
        config = ConfigStorage(Path(settings.DATA_FOLDER))
        await config.initialize(config_file)
        hass = await open_hass_connection(config)
        result.hass = hass
        result.config = EnergyAssistantConfig(config, await hass.get_config() if hass is not None else {})
        if hass is not None:
            hass.read_states()
            optimizer = EmhassOptimizer(settings.DATA_FOLDER, config, hass, await hass.get_location())
            result.optimizer = optimizer
            app.optimizer = optimizer  # type: ignore

        mqtt_connection: MqttConnection | None = create_mqtt_connection(config)
        result.mqtt = mqtt_connection

        home_config = config.home
        if home_config is not None and home_config.get("name") is not None:
            home = Home(config, session_storage, device_type_registry)
            result.home = home
            app.home = home  # type: ignore
            if mqtt_connection is not None:
                subscribe_mqtt_topics(mqtt_connection, home)

            async with async_session() as session:
                await db.update_devices(home, session, session_storage, device_type_registry)

                await db.restore_home_state(home, session)
        else:
            logger.error(f"home not found in config file: {config}")
        logger.info("Initialization completed")
    except Exception:
        logger.exception("Initialization of the app failed")
    return result


async def optimize(optimizer: EmhassOptimizer) -> None:
    """Optimize the forecast."""
    try:
        optimizer.forecast_model_fit(True)
    except Exception:
        logging.exception(
            "Optimization of the power consumption forecast model failed, probably due to missing history data in Home Assistant.",
        )


async def async_daily_optimize(ea: EnergyAssistant) -> None:
    """Optimize once a day."""
    try:
        optimizer = ea.optimizer
        if optimizer is not None:
            logging.info("Start optimizer run")
            await optimizer.async_dayahead_forecast_optim()
    except Exception:
        logging.exception("Daily optimization run failed")


@app.get("/check", include_in_schema=False)
async def health() -> JSONResponse:
    """Test the web server with a ping."""
    return JSONResponse({"message": "It worked!!"})


# This needs to be the last mount
frontend_dir = locate_frontend()
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


def main() -> None:
    """Start energy assistant."""
    import uvicorn

    try:
        alembic_config = Path(__file__).parent / "alembic.ini"

        alembic_args = [
            "-c",
            str(alembic_config),
            "--raiseerr",
            "upgrade",
            "head",
        ]
        alembic.config.main(argv=alembic_args)  # type: ignore
    except Exception:
        print("Alembic Migration failed")
        logging.exception("Alembic Migration failed")

    uvicorn.run(app, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
