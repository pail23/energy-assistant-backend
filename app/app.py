"""Main module for the energy assistant application."""
import asyncio
from datetime import date
import json
import logging
import os

from aiohttp import web
from devices import Device
from devices.homeassistant import (
    Home,
    Homeassistant,
    HomeassistantDevice,
    StiebelEltronDevice,
)
import socketio
from storage import Database
import yaml

sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins="*")
app = web.Application()
sio.attach(app)


async def async_handle_state_update():
    """Read the values from home assistant and process the update."""
    try:
        global hass
        hass.update_states()
        home.update_state_from_hass(hass)
        await asyncio.gather(sio.emit('refresh', {'data': get_home_message()}), db.store_home_state(home))
    except Exception as ex:
        logging.error("error during sending refresh", ex)


async def background_task():
    """Periodically read the values from home assistant and process the update."""
    last_update = date.today()
    while True:
        await sio.sleep(10)
        # delta_t = datetime.now().timestamp()
        # print("Start refresh from home assistant")
        today = date.today()
        try:
            if today != last_update:
                global home
                home.store_energy_snapshot()
            last_update = today
            await async_handle_state_update()
        except Exception as ex:
            logging.error("error in the background task: ", ex)
        #print(f"refresh from home assistant completed in {datetime.now().timestamp() - delta_t} s")

def get_self_sufficiency(consumed_solar_energy:float, consumed_energy: float) -> float:
    """Calulate the self sufficiency value."""
    return min(round(consumed_solar_energy / consumed_energy * 100) if consumed_energy > 0 else 0.0, 100)

def get_device_message(device: Device) -> dict:
    """Generate the update data message for a device."""
    if device.energy_snapshot is not None:
        consumed_energy_today = device.consumed_energy - device.energy_snapshot.consumed_energy
        consumed_solar_energy_today = device.consumed_solar_energy - device.energy_snapshot.consumed_solar_energy
    else:
        consumed_energy_today = 0
        consumed_solar_energy_today = 0
    result = {
        "name": device.name,
        "type": device.__class__.__name__,
        "icon": device.icon,
        "power": device.power,
        "overall": {
            "consumed_solar_energy": device.consumed_solar_energy,
            "consumed_energy": device.consumed_energy,
            "self_sufficiency": get_self_sufficiency(device.consumed_solar_energy, device.consumed_energy)
        },
        "today": {
            "consumed_solar_energy":  consumed_solar_energy_today,
            "consumed_energy": consumed_energy_today,
            "self_sufficiency": get_self_sufficiency(consumed_solar_energy_today, consumed_energy_today)
        },
    }
    if isinstance(device, StiebelEltronDevice):
        result["actual_temperature"] = device.actual_temperature
    return result


def get_home_message():
    """Generate the update data message for a home."""
    devices_message = []
    global home
    for device in home.devices:
        if not isinstance(device, StiebelEltronDevice):
            devices_message.append(get_device_message(device))
    heat_pump_message = []
    for device in home.devices:
        if isinstance(device, StiebelEltronDevice):
            heat_pump_message.append(get_device_message(device))

    if home.energy_snapshop is not None:
        consumed_energy_today = home.consumed_energy - home.energy_snapshop.consumed_energy
        consumed_solar_energy_today = home.consumed_solar_energy - home.energy_snapshop.consumed_solar_energy
    else:
        consumed_energy_today = 0
        consumed_solar_energy_today = 0
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
            "self_sufficiency": get_self_sufficiency(home.consumed_solar_energy,home.consumed_energy)
        },
        "today": {
            "consumed_solar_energy":  consumed_solar_energy_today,
            "consumed_energy": consumed_energy_today,
            "self_sufficiency": get_self_sufficiency(consumed_solar_energy_today, consumed_energy_today)
        },
        "devices": devices_message,
        "heat_pumps": heat_pump_message
    }
    return json.dumps(home_message)


@sio.event
async def connect(sid, environ):
    """Handle the connect of a client via socket.io to the server."""
    logging.info(f"connect {sid}")
    await sio.emit('refresh', {'data': get_home_message()}, room=sid)


@sio.event
def disconnect(sid):
    """Handle the disconnect of a client via socket.io to the server."""
    logging.info(f"Client disconnected {sid}")


async def init_app():
    """Initialize the application."""
    # opts, args = getopt.getopt(sys.argv[1:],"c:",["config="])
    config_file = "/config/energy_assistant.yaml"
   # for opt, arg in opts:
   #   if opt in ("-c", "--config"):
   #      config_file = arg

    if config_file is not None:
        logfilename = os.path.join(os.path.dirname(
            config_file), 'energy-assistant.log')
    else:
        logfilename = 'energy-assistant.log'
    logging.basicConfig(filename=logfilename,
                        encoding='utf-8', level=logging.DEBUG)

    logging.info("Hello from Energy Assistant")

    global db
    db = Database()
    await db.create_db_engine()

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
                        global hass
                        hass = Homeassistant(url, token)
                        hass.update_states()

                global home
                home_config = config.get("home")
                if home_config is not None and home_config.get("name") is not None:
                    home = Home(home_config.get("name"), "sensor.solaredge_i1_ac_power",
                                "sensor.solaredge_m1_ac_power", "sensor.solaredge_i1_ac_energy_kwh", "sensor.solaredge_m1_imported_kwh", "sensor.solaredge_m1_exported_kwh")
                    home.add_device(HomeassistantDevice(
                        "Keba", "sensor.keba_charge_power", "sensor.keba_total_charged_energy", "mdi-car-electric"))
                    home.add_device(StiebelEltronDevice(
                        "Warm Wasser", "binary_sensor.stiebel_eltron_isg_is_heating_boiler", "sensor.stiebel_eltron_isg_consumed_water_heating_total", "sensor.stiebel_eltron_isg_consumed_water_heating_today", "sensor.stiebel_eltron_isg_actual_temperature_water"))
                    home.add_device(StiebelEltronDevice(
                        "Heizung", "binary_sensor.stiebel_eltron_isg_is_heating","sensor.stiebel_eltron_isg_consumed_heating_total", "sensor.stiebel_eltron_isg_consumed_heating_today", "sensor.stiebel_eltron_isg_actual_temperature_fek"))
                    home.add_device(HomeassistantDevice(
                        "Tumbler", "sensor.tumbler_power", "sensor.laundry_tumbler_energy", "mdi-tumble-dryer"))
                    await db.restore_home_state(home)
                    home.update_state_from_hass(hass)
                    await async_handle_state_update()
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
    sio.start_background_task(background_task)
    return app


if __name__ == '__main__':
    web.run_app(init_app(), port=5000)
