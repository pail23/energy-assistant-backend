"""Main module for the energy assistant application."""
import asyncio
from datetime import date
import json
import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_socketio import SocketManager  # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession
import yaml

from app.api.device import OTHER_DEVICE
from app.api.main import router as api_router
from app.devices import Device
from app.devices.homeassistant import Home, Homeassistant, StiebelEltronDevice
from app.settings import settings
from app.storage import Database, get_async_session

app = FastAPI(title="energy-assistant")
sio = SocketManager(app=app, cors_allowed_origins="*")

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


async def async_handle_state_update(home: Home, hass: Homeassistant, db: Database, session: AsyncSession) -> None:
    """Read the values from home assistant and process the update."""
    try:
        hass.update_states()
        home.update_state_from_hass(hass)
        # print("Send refresh: " + get_home_message(home))
        if db:
            if home:
                await asyncio.gather(sio.emit('refresh', {'data': get_home_message(home)}), db.store_home_state(home, session))
            else:
                logging.error(
                    "The variable home is None in async_handle_state_update")
        else:
            logging.error(
                "The variable db is None in async_handle_state_update")
    except Exception as ex:
        logging.error("error during sending refresh", ex)


async def background_task(home: Home, hass: Homeassistant, db: Database) -> None:
    """Periodically read the values from home assistant and process the update."""
    last_update = date.today()
    async_session = await get_async_session()
    while True:
        await sio.sleep(10)
        # delta_t = datetime.now().timestamp()
        # print("Start refresh from home assistant")
        today = date.today()
        try:
            if today != last_update:
                home.store_energy_snapshot()
            last_update = today
            async with async_session() as session:
                await async_handle_state_update(home, hass, db, session)
        except Exception as ex:
            logging.error("error in the background task: ", ex)
        # print(f"refresh from home assistant completed in {datetime.now().timestamp() - delta_t} s")


def get_self_sufficiency(consumed_solar_energy: float, consumed_energy: float) -> float:
    """Calulate the self sufficiency value."""
    return min(round(consumed_solar_energy / consumed_energy * 100) if consumed_energy > 0 else 0.0, 100)


def get_device_message(device: Device) -> dict:
    """Generate the update data message for a device."""
    if device.energy_snapshot is not None:
        consumed_energy_today = device.consumed_energy - \
            device.energy_snapshot.consumed_energy
        consumed_solar_energy_today = device.consumed_solar_energy - \
            device.energy_snapshot.consumed_solar_energy
    else:
        consumed_energy_today = 0
        consumed_solar_energy_today = 0
    result = {
        # "name": device.name,
        "device_id": str(device.id),
        "type": device.__class__.__name__,
        # "icon": device.icon,
        "power": device.power,
        "available": device.available,
        "today": {
            "consumed_solar_energy":  consumed_solar_energy_today,
            "consumed_energy": consumed_energy_today,
            "self_sufficiency": get_self_sufficiency(consumed_solar_energy_today, consumed_energy_today)
        },
    }
    if isinstance(device, StiebelEltronDevice):
        result["actual_temperature"] = device.actual_temperature
        result["state"] = device.state
    return result


def get_home_message(home: Home) -> str:
    """Generate the update data message for a home."""
    devices_messages = []
    if home.energy_snapshop is not None:
        consumed_energy_today = home.consumed_energy - \
            home.energy_snapshop.consumed_energy
        consumed_solar_energy_today = home.consumed_solar_energy - \
            home.energy_snapshop.consumed_solar_energy
    else:
        consumed_energy_today = 0
        consumed_solar_energy_today = 0

    other_power = home.home_consumption_power
    other_consumed_energy = consumed_energy_today
    other_consumed_solar_energy = consumed_solar_energy_today
    for device in home.devices:
        if not isinstance(device, StiebelEltronDevice):
            device_message = get_device_message(device)
            devices_messages.append(device_message)
            other_power = other_power - device.power
            other_consumed_energy = other_consumed_energy - \
                device_message["today"]["consumed_energy"]
            other_consumed_solar_energy = other_consumed_solar_energy - \
                device_message["today"]["consumed_solar_energy"]

    heat_pump_message = []
    for device in home.devices:
        if isinstance(device, StiebelEltronDevice):
            device_message = get_device_message(device)
            heat_pump_message.append(device_message)
            other_power = other_power - device.power
            other_consumed_energy = other_consumed_energy - \
                device_message["today"]["consumed_energy"]
            other_consumed_solar_energy = other_consumed_solar_energy - \
                device_message["today"]["consumed_solar_energy"]

    other_device = {
        "device_id": str(OTHER_DEVICE),
        "type": "other_device",
        "power": other_power,
        "available": True,
        "today": {
            "consumed_solar_energy":  other_consumed_solar_energy,
            "consumed_energy": other_consumed_energy,
            "self_sufficiency": get_self_sufficiency(other_consumed_solar_energy, other_consumed_energy)
        },
    }
    devices_messages.append(other_device)

    home_message = {
        "name": home.name,
        "power": {
            "solar_production": home.solar_production_power,
            "grid_supply": home.grid_supply_power,
            "solar_self_consumption": home.solar_self_consumption_power,
            "home_consumption": home.home_consumption_power,
            "self_sufficiency": round(home.self_sufficiency * 100)
        },
        "overall": {
            "consumed_solar_energy": home.consumed_solar_energy,
            "consumed_energy": home.consumed_energy,
            "self_sufficiency": get_self_sufficiency(home.consumed_solar_energy, home.consumed_energy)
        },
        "today": {
            "consumed_solar_energy":  consumed_solar_energy_today,
            "consumed_energy": consumed_energy_today,
            "self_sufficiency": get_self_sufficiency(consumed_solar_energy_today, consumed_energy_today)
        },
        "devices": devices_messages,
        "heat_pumps": heat_pump_message
    }
    return json.dumps(home_message)


@app.sio.event  # type: ignore
async def connect(sid, environ):
    """Handle the connect of a client via socket.io to the server."""
    logging.info(f"connect {sid}")
    await sio.emit('refresh', {'data': get_home_message(app.home)}, room=sid)


@app.sio.event  # type: ignore
def disconnect(sid):
    """Handle the disconnect of a client via socket.io to the server."""
    logging.info(f"Client disconnected {sid}")


async def init_app() -> None:
    """Initialize the application."""
    app.home = None  # type: ignore
    app.hass = None  # type: ignore
    app.db = None  # type: ignore

    config_file = settings.CONFIG_FILE  # "/config/energy_assistant.yaml"
    logfilename = settings.LOG_FILE

    rfh = RotatingFileHandler(
        filename=logfilename,
        mode='a',
        maxBytes=5*1024*1024,
        backupCount=2,
        encoding='utf-8'
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)-25s %(levelname)-8s %(message)s",
        datefmt="%y-%m-%d %H:%M:%S",
        handlers=[
            rfh
        ]
    )

    logging.info("Hello from Energy Assistant")

    async_session = await get_async_session()
    db = Database()
    app.db = db  # type: ignore

    logging.info(f"Loading config file {config_file}")
    try:
        with open(config_file) as stream:
            logging.debug(f"Successfully opened config file {config_file}")
            try:
                config = yaml.safe_load(stream)
                logging.debug(f"config file {config_file} successfully loaded")
            except yaml.YAMLError as ex:
                logging.error(ex)
            except Exception as ex:
                logging.error(ex)
            else:
                hass_config = config.get("homeassistant")
                if hass_config is not None:
                    url = hass_config.get("url")
                    token = hass_config.get("token")
                    if url is not None and token is not None:
                        hass = Homeassistant(url, token)
                        app.hass = hass  # type: ignore
                        hass.update_states()

                home_config = config.get("home")
                if home_config is not None and home_config.get("name") is not None:
                    home = Home(home_config)
                    app.home = home  # type: ignore
                    async with async_session() as session:
                        await db.update_devices(home, session)

                        await db.restore_home_state(home, session)

                    """
                    mqtt_config = config.get("mqtt")
                    if mqtt_config is not None:
                        homeassistant_host = mqtt_config.get("host")

                        topic = mqtt_config.get("topic")
                        global energyassistant_topic
                        if topic is not None:
                            energyassistant_topic = topic
                        try:
                            mqttc = mqtt.Client("energy_assistant"+str(random.randrange(1024)), 1883, 45)
                            mqttc.username_pw_set(mqtt_config.get(
                                "username"), mqtt_config.get("password"))
                            mqttc.will_set(f"{energyassistant_topic}/status",
                                        payload="offline", qos=0, retain=True)
                            mqttc.on_message = on_message
                            mqttc.on_connect = on_connect
                            mqttc.on_disconnect = on_disconnect
                            mqttc.connect(homeassistant_host)
                            mqttc.loop_start()
                        except Exception as ex:
                            logging.error("Error while connecting mqtt ", ex)
                    else:
                        logging.error(f"mqtt not found in config file: {config}")
                        """
                else:
                    logging.error(f"home not found in config file: {config}")
                logging.info("Initialization completed")
    except Exception as ex:
        logging.error(ex)


@app.on_event("startup")
async def startup() -> None:
    """Statup call back to initialize the app and start the background task."""
    await init_app()
    sio.start_background_task(
        background_task, app.home, app.hass, app.db)  # type: ignore


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Stop call back to stop the app."""
    print("Shutdown app")


@app.get("/check", include_in_schema=False)
async def health() -> JSONResponse:
    """Test the web server with a ping."""
    return JSONResponse({"message": "It worked!!"})

# This needs to be the last mount
app.mount("/", StaticFiles(directory="client", html=True), name="frontend")


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
