"""Helper classes for web socket."""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from energy_assistant.api.device import OTHER_DEVICE
from energy_assistant.devices.device import Device
from energy_assistant.devices.home import Home

from .constants import ROOT_LOGGER_NAME

LOGGER = logging.getLogger(ROOT_LOGGER_NAME)

ws_router = APIRouter()


class WebSocketConnectionManager:
    """Web Socket connection manager."""

    def __init__(self) -> None:
        """Initialize the web socket connection manager instance."""
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Connect handler."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Disconnect handler."""
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """Send a message to one web socket."""
        await websocket.send_text(message)

    async def broadcast(self, message: str) -> None:
        """Broadcast a message."""
        for connection in self.active_connections:
            await connection.send_text(message)


ws_manager = WebSocketConnectionManager()


def get_self_sufficiency(consumed_solar_energy: float, consumed_energy: float) -> float:
    """Calculate the self sufficiency value."""
    return min(round(consumed_solar_energy / consumed_energy * 100) if consumed_energy > 0 else 0.0, 100)


def get_self_consumption(produced_solar_energy: float, consumed_solar_energy: float) -> float:
    """Calculate the self sufficiency value."""
    return min(
        round(consumed_solar_energy / produced_solar_energy * 100) if produced_solar_energy > 0 else 0.0,
        100,
    )


def get_device_message(device: Device) -> dict:
    """Generate the update data message for a device."""
    if device.energy_snapshot is not None:
        consumed_energy_today = device.consumed_energy - device.energy_snapshot.consumed_energy
        consumed_solar_energy_today = device.consumed_solar_energy - device.energy_snapshot.consumed_solar_energy
    else:
        consumed_energy_today = 0
        consumed_solar_energy_today = 0
    result = {
        "device_id": str(device.id),
        "type": device.__class__.__name__,
        "power": device.power,
        "available": device.available,
        "today": {
            "consumed_solar_energy": consumed_solar_energy_today,
            "consumed_energy": consumed_energy_today,
            "self_sufficiency": get_self_sufficiency(consumed_solar_energy_today, consumed_energy_today),
        },
    }
    result["attributes"] = device.attributes
    return result


def get_home_message(home: Home) -> str:
    """Generate the update data message for a home."""
    devices_messages = []
    if home.energy_snapshop is not None:
        consumed_energy_today = home.consumed_energy - home.energy_snapshop.consumed_energy
        consumed_solar_energy_today = home.consumed_solar_energy - home.energy_snapshop.consumed_solar_energy
        produced_solar_energy_today = home.produced_solar_energy - home.energy_snapshop.produced_solar_energy
    else:
        consumed_energy_today = 0
        consumed_solar_energy_today = 0
        produced_solar_energy_today = 0

    other_power = home.home_consumption_power
    other_consumed_energy = consumed_energy_today
    other_consumed_solar_energy = consumed_solar_energy_today
    for device in home.devices:
        device_message = get_device_message(device)
        devices_messages.append(device_message)
        other_power = max(other_power - device.power, 0.0)
        other_consumed_energy = max(other_consumed_energy - device_message["today"]["consumed_energy"], 0.0)
        other_consumed_solar_energy = max(
            other_consumed_solar_energy - device_message["today"]["consumed_solar_energy"],
            0.0,
        )

    other_device = {
        "device_id": str(OTHER_DEVICE),
        "type": "other_device",
        "power": other_power,
        "available": True,
        "today": {
            "consumed_solar_energy": other_consumed_solar_energy,
            "consumed_energy": other_consumed_energy,
            "self_sufficiency": get_self_sufficiency(other_consumed_solar_energy, other_consumed_energy),
        },
    }
    devices_messages.append(other_device)

    home_message = {
        "name": home.name,
        "power": {
            "solar_production": home.solar_production_power,
            "grid_supply": home.grid_imported_power,
            "solar_self_consumption": home.solar_self_consumption_power,
            "home_consumption": home.home_consumption_power,
            "self_sufficiency": round(home.self_sufficiency * 100),
            "self_consumption": round(home.self_consumption * 100),
        },
        "today": {
            "consumed_solar_energy": consumed_solar_energy_today,
            "consumed_energy": consumed_energy_today,
            "produced_solar_energy": produced_solar_energy_today,
            "self_sufficiency": get_self_sufficiency(consumed_solar_energy_today, consumed_energy_today),
            "self_consumption": get_self_consumption(produced_solar_energy_today, consumed_solar_energy_today),
        },
        "devices": devices_messages,
    }
    return json.dumps(home_message)


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Web Socket end point for broad casts."""
    await ws_manager.connect(websocket)
    try:
        if hasattr(websocket.app, "energy_assistant"):
            ea = websocket.app.energy_assistant  # type: ignore
            await ws_manager.broadcast(get_home_message(ea.home))

        while True:
            data = await websocket.receive_text()
            LOGGER.error(f"received unexpected data from frontend: {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
