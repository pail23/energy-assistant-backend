# Energy Assistant Configuration file

The `energy_assistant.yaml` file is used to configure Energy Assistant. It consists of the followin sections.

# Home

Configure the main attributes of your home.

Example:

```
home:
  name: "My Home"
  solar_power: sensor.solaredge_i1_ac_power
  solar_energy: sensor.solaredge_i1_ac_energy_kwh
  grid_supply_power: sensor.solaredge_m1_ac_power
  imported_energy: sensor.solaredge_m1_imported_kwh
  exported_energy: sensor.solaredge_m1_exported_kwh
  devices:
    - name: Evcc loadpoint 1
      id: 7d480adc-2c45-4de9-8f36-063c5dea0253
      type: evcc
      evcc_topic: "evcc"
      load_point_id: 1
      store_sessions: true
    - name: Tumbler
      id: 75203c88-216f-4712-8a94-80513793f7e1
      type: power-state-device
      power: sensor.tumbler_power
      energy: sensor.tumbler_energy
      energy_scale: 0.001
      store_sessions: true
      manufacturer: v-zug
      model: Adora TS WP
    - name: Server
      id: eb6b3f0a-1175-4ff3-9ebe-8c22663cba48
      type: homeassistant
      icon: mdi-server-network
      power: sensor.server_power
      energy: sensor.server_energy
      energy_scale: 0.001
```

# Mqtt

The mqtt configuration is only needed in case you would like to interface with [evcc](https://evcc.io/).

Example:

```
mqtt:
  host: homeassistant.stadel15.net
  username: smarthome
  password: smarthome!23
  topic: energyassistant
```

# Emhass

The Emhass configuration section is described in the [Emhass documentation](https://emhass.readthedocs.io/en/latest/config.html).

The following keys in the Emhass configuration are provided by Energy Assistant itself. In case you are using those keys, Energy Assistant will overwrite the values.

# Home Assistant

This section is only used in case you run Energy Assistant stand alone (not as Home Assistant addon).

Example:

```
homeassistant:
  url: https://homeassistant.example.net
  token: "your long lived home assistant token"
```
