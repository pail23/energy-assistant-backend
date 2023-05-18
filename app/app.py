from threading import Lock
from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler

import yaml
import json
import paho.mqtt.client as mqtt
from devices import Device, EvccDevice, Home
from datetime import date
import logging

logging.basicConfig(filename='energy-assistant.log', encoding='utf-8', level=logging.DEBUG)

# instantiate the app
db = SQLAlchemy()

app = Flask(__name__)
app.config.from_object(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config.from_prefixed_env()

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///energy_assistant.db"

db.init_app(app)
socketio = SocketIO(app, async_mode=None, cors_allowed_origins="*")


# initialize scheduler
scheduler = APScheduler()




class DeviceMeasurement(db.Model):
    """Data model for a measurement"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    solar_energy = db.Column(db.Float)
    solar_consumed_energy = db.Column(db.Float)
    date = db.Column(db.Date)


# cron examples
@scheduler.task("cron", id="do_job_2", minute="*")
def job2():
    """Sample job 2."""
    logging.info("Job 2 executed")


# interval examples
@scheduler.task("interval", id="do_job_1", seconds=30, misfire_grace_time=900)
def job1():
    """Sample job 1."""
    logging.info("Job 1 executed")  



energyassistant_topic = "energyassistant"
home = None

# enable CORS
CORS(app, resources={r'/*': {'origins': '*'}})




@socketio.event
def connect():
    logging.info('Socket IO client connected')
    emit('connection', {'data': '{"Connected": true}', 'count': 0})


@socketio.on('disconnect')
def test_disconnect():
    logging.info('Socket IO client disconnected')

# devices route
@app.route('/api/devices', methods=['GET'])
def get_devices():
    devices_message = []
    for device in home.devices:
        devices_message.append(
            {"name": device.name, "state": device.state, "icon": "mdi:mdi-car-electric"})
    return jsonify(devices_message)


def get_home_message():
    devices_message = []
    for device in home.devices:
        devices_message.append(
            {
                "name": device.name, 
                "state": device.state, 
                "icon": "mdi:mdi-car-electric", 
                "solar_energy": device.solar_energy,
                "consumed_energy": device.consumed_energy,
                "self_sufficiency_today": round(home.solar_energy / home.consumed_energy * 100) if home.consumed_energy > 0 else 0.0,
            })    
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
        "devices" : devices_message
    }
    return json.dumps(home_message)

@app.route('/api/home', methods=['GET'])
def get_home():
    return get_home_message()


def store_measurement(device: Device):
    today = date.today()
    device_measurement = DeviceMeasurement.query.filter_by(name=device.name, date=today).first()
    if device_measurement is None:
        device_measurement = DeviceMeasurement(name = device.name, date=today)
        db.session.add(device_measurement)
    device_measurement.solar_energy = device.solar_energy
    device_measurement.solar_consumed_energy = device.consumed_energy

def on_message(client, userdata, message):
   
    home.update_state(message.topic, str(message.payload.decode("utf-8")))
    try:
        socketio.emit('refresh',
                  {'data': get_home_message()})
    except Exception as ex:
        logging.error("error during sending refresh", ex)
    try:
        with app.app_context():
            store_measurement(home)

            for device in home.devices:
                store_measurement(device)
            
            db.session.commit()
    except Exception as ex:
        logging.error("error during updating database with measurements", ex)


def on_disconnect(client, userdata, rc):
    if rc != 0:
        logging.error('Unexpected disconnection from MQTT, trying to reconnect')


def on_connect(client, userdata, flags, rc):
    logging.info("mqtt connected")
    client.publish("{energyassistant_topic}/status", "online")
    for topic in home.mqtt_topics():
        client.subscribe(topic + "/#", 0)


def initialize():
    logging.info("Hello from Energy Assistant")
    with app.app_context():
        db.create_all()    
    # if you don't wanna use a config, you can set options here:
    scheduler.api_enabled = True
    scheduler.init_app(app)
    scheduler.start()    
    config_file = app.config.get("CONFIGFILE")
    if config_file is None:
        config_file = "/config/energy_assistant.yaml"
    
    logging.info(f"Loading config file {config_file}")
    try:
        with open(config_file, "r") as stream:
            try:
                config = yaml.safe_load(stream)
                logging.debug(f"config file {config_file} successfully loaded")
            except yaml.YAMLError as exc:
                logging.error(exc)
            except Exception as exc:
                logging.error(exc)
            else:
                global home
                home_config = config.get("home")
                if home_config is not None and home_config.get("name") is not None:
                    home = Home(home_config.get("name"), "homeassistant/sensor/solaredge_i1_ac_power",
                    "homeassistant/sensor/solaredge_m1_ac_power")
                    home.add_device(EvccDevice(
                        "Keba", "evcc/loadpoints/1/chargePower"))

                    mqtt_config = config.get("mqtt")
                    if mqtt_config is not None:
                        homeassistant_host = mqtt_config.get("host")

                        topic = mqtt_config.get("topic")
                        global energyassistant_topic
                        if topic is not None:
                            energyassistant_topic = topic
                        try:
                            mqttc = mqtt.Client("energy_assistant", 1883, 45)
                            mqttc.username_pw_set(mqtt_config.get(
                                "username"), mqtt_config.get("password"))
                            mqttc.will_set(f"{energyassistant_topic}/status",
                                        payload="offline", qos=0, retain=True)
                            mqttc.connect(homeassistant_host)
                            mqttc.on_message = on_message
                            mqttc.on_connect = on_connect
                            mqttc.on_disconnect = on_disconnect
                            mqttc.loop_start()
                        except Exception as ex:
                            logging.error("Error while connecting mqtt ", ex)
                    else:
                        logging.error(f"mqtt not found in config file: {config}")
                else:
                    logging.error(f"home not found in config file: {config}");
                logging.info("Initialization completed")
    except Exception as ex:
        logging.error(ex)

initialize()

if __name__ == '__main__':
    socketio.run(app)
