from aiohttp import web
import socketio
import json
import random
import logging
import os
import yaml
import sys
import getopt

from devices import Device
from devices.mqtt import EvccDevice
from devices.homeassistant import Homeassistant, HomeassistantDevice, StiebelEltronDevice, Home
from storage import Database

sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins="*")
app = web.Application()
sio.attach(app)


async def async_handle_state_update():
    try:
        await sio.emit('refresh', {'data': get_home_message()})
    except Exception as ex:
        logging.error("error during sending refresh", ex)
    try:
        await db.store_home_state(home)
    except Exception as ex:
        logging.error("error during updating database with measurements", ex)

async def background_task():
    """Example of how to send server generated events to clients."""
    while True:
        await sio.sleep(10)
        try:
            global hass
            home.update_state_from_hass(hass)
            await async_handle_state_update()
        except Exception as ex:
            logging.error("error in the background task: ", ex)

async def index(request):
    """Serve the client-side application."""
    with open('/workspaces/backend/static/index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')


def get_device_message(device: Device) -> dict:
    result = {
        "name": device.name,
        "type": device.__class__.__name__,
        "state": device.state,
        "icon": device.icon,
        "solar_energy": device.solar_energy,
        "consumed_energy": device.consumed_energy,
        "self_sufficiency_today": round(home.solar_energy / home.consumed_energy * 100) if home.consumed_energy > 0 else 0.0,
        "extra_attibutes": json.dumps(device.extra_attributes)
    }
    if isinstance(device, StiebelEltronDevice):
        result["actual_temperature"] = device.actual_temperature
    return result


def get_home_message():
    devices_message = []
    global home
    for device in home.devices:
        if not isinstance(device, StiebelEltronDevice):
            devices_message.append(get_device_message(device))
    heat_pump_message = []
    for device in home.devices:
        if isinstance(device, StiebelEltronDevice):
            heat_pump_message.append(get_device_message(device))
    home_message = {
        "name": home.name,
        "solar_production": home.solar_production,
        "grid_supply": home.grid_supply,
        "solar_self_consumption": home.solar_self_consumption,
        "home_consumption": home.home_consumption,
        "self_sufficiency": round(home.self_sufficiency * 100),
        "solar_energy": home.solar_energy,
        "consumed_energy": home.consumed_energy,
        "self_sufficiency_today": round(home.solar_energy / home.consumed_energy * 100) if home.consumed_energy > 0 else 0.0,
        "devices": devices_message,
        "heat_pumps": heat_pump_message
    }
    return json.dumps(home_message)


@sio.event
async def connect(sid, environ):
    print("connect ", sid)
    await sio.emit('refresh', {'data': get_home_message()}, room=sid)


@sio.event
def disconnect(sid):
    print('Client disconnected')



async def init_app():
    #opts, args = getopt.getopt(sys.argv[1:],"c:",["config="])
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
        with open(config_file, "r") as stream:
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
                                "sensor.solaredge_m1_ac_power")
                    home.add_device(HomeassistantDevice(
                        "Keba", "sensor.keba_charge_power"))
                    home.add_device(StiebelEltronDevice(
                        "Warm Wasser", "binary_sensor.stiebel_eltron_isg_is_heating_boiler", "sensor.stiebel_eltron_isg_actual_temperature_water"))
                    home.add_device(StiebelEltronDevice(
                        "Heizung", "binary_sensor.stiebel_eltron_isg_is_heating", "sensor.stiebel_eltron_isg_actual_temperature_fek"))
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
