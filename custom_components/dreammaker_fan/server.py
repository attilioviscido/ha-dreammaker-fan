"""TCP server that impersonates the Dream Maker cloud (cloud1.dm-maker.com).

Ported into a Home Assistant custom_component from the standalone
dmiot2mqtt project (https://github.com/klada/dmiot2mqtt by klada, GPLv3).
Instead of bridging to MQTT, state changes are pushed directly to Home
Assistant entities via the dispatcher, and commands are sent back down the
same TCP connection.
"""
from __future__ import annotations

import asyncio
import copy
import json
import logging
from typing import Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ACTION_ACK,
    ACTION_COMMAND,
    ACTION_STATE_PUSH,
    DEFAULT_PORT,
    RESOURCE_STATE,
    RESOURCE_STATUS,
    SIGNAL_NEW_DEVICE,
)

_LOGGER = logging.getLogger(__name__)

REPLY_TEMPLATE = {"action": ACTION_ACK, "resource_id": 0, "version": "zeico_3.0.0", "code": 0}
COMMAND_TEMPLATE = {"action": ACTION_COMMAND, "resource_id": RESOURCE_STATE, "version": "zeico_3.0.0", "msg_id": 0}


class DreamMakerDevice:
    """Represents one connected Dream Maker fan (keyed by its LAN IP)."""

    def __init__(self, hass: HomeAssistant, device_ip: str, writer: asyncio.StreamWriter):
        self.hass = hass
        self.device_ip = device_ip
        self._writer = writer
        self.state: dict = {}
        self.heartbeat: dict = {}
        self.available = True
        self._listeners: list[Callable[[], None]] = []

    @property
    def unique_id(self) -> str:
        return self.device_ip.replace(".", "_")

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register an entity update callback, returns an unsubscribe function."""
        self._listeners.append(callback)

        def _remove():
            if callback in self._listeners:
                self._listeners.remove(callback)

        return _remove

    def _notify(self):
        for callback in list(self._listeners):
            callback()

    def update_state(self, data: dict):
        self.state.update(data)
        self.available = True
        self._notify()

    def update_heartbeat(self, data: dict):
        self.heartbeat.update(data)
        self.available = True
        self._notify()

    def mark_unavailable(self):
        self.available = False
        self._notify()

    async def async_send_command(self, command_data: dict):
        if self._writer.is_closing():
            _LOGGER.warning("Cannot send command to %s: connection closed", self.device_ip)
            return
        message = copy.copy(COMMAND_TEMPLATE)
        message["data"] = command_data
        payload = json.dumps(message).encode()
        self._writer.write(payload)
        await self._writer.drain()


class DreamMakerServer:
    """Owns the asyncio TCP server and the set of known devices."""

    def __init__(self, hass: HomeAssistant, entry_id: str, port: int = DEFAULT_PORT):
        self.hass = hass
        self.entry_id = entry_id
        self.port = port
        self.devices: dict[str, DreamMakerDevice] = {}
        self._server: asyncio.AbstractServer | None = None

    async def async_start(self):
        self._server = await asyncio.start_server(self._handle_client, "0.0.0.0", self.port)
        _LOGGER.info("Dream Maker fan server listening on port %s", self.port)

    async def async_stop(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        device_ip = addr[0] if addr else "unknown"
        _LOGGER.info("Fan %s connected", device_ip)

        device = self.devices.get(device_ip)
        is_new = device is None
        if is_new:
            device = DreamMakerDevice(self.hass, device_ip, writer)
            self.devices[device_ip] = device
        else:
            device._writer = writer  # reconnected on a new socket
            device.available = True

        try:
            authenticated = await self._authenticate(reader, writer, device)
            if not authenticated:
                return

            if is_new:
                async_dispatcher_send(self.hass, f"{SIGNAL_NEW_DEVICE}_{self.entry_id}", device)

            while not reader.at_eof():
                message = await self._read_message(reader)
                if not message:
                    continue
                await self._handle_message(writer, device, message)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError) as err:
            _LOGGER.info("Fan %s disconnected: %s", device_ip, err)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error handling fan %s", device_ip)
        finally:
            device.mark_unavailable()
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    async def _authenticate(self, reader, writer, device: DreamMakerDevice) -> bool:
        while not reader.at_eof():
            message = await self._read_message(reader)
            if not message:
                continue
            if message.get("action") == 1 and message.get("resource_id") == 2000:
                _LOGGER.info("Provisioning request from %s", device.device_ip)
                response = copy.copy(REPLY_TEMPLATE)
                response["resource_id"] = 2000
                response["action"] = ACTION_ACK
                response["data"] = {
                    "device_key": "0000000000000000",
                    "device_id": "000000000000000000000000",
                }
                await self._send(writer, response)
            elif message.get("action") == 1 and message.get("resource_id") == 2001:
                _LOGGER.debug("Auth handshake from %s", device.device_ip)
                await self._ack(writer, message)
                return True
        return False

    async def _handle_message(self, writer, device: DreamMakerDevice, message: dict):
        await self._ack(writer, message)
        resource_id = message.get("resource_id")
        data = message.get("data", {})
        if resource_id == RESOURCE_STATUS:
            device.update_heartbeat(data)
        elif resource_id == RESOURCE_STATE:
            device.update_state(data)

    @staticmethod
    async def _read_message(reader: asyncio.StreamReader) -> dict:
        data = await reader.read(1024)
        if not data:
            return {}
        try:
            return json.loads(data.decode())
        except json.JSONDecodeError:
            _LOGGER.debug("Invalid JSON received, ignoring")
            return {}

    @staticmethod
    async def _send(writer: asyncio.StreamWriter, data: dict):
        writer.write(json.dumps(data).encode())
        await writer.drain()

    async def _ack(self, writer: asyncio.StreamWriter, message: dict):
        response = copy.copy(REPLY_TEMPLATE)
        response["resource_id"] = message.get("resource_id", 0)
        await self._send(writer, response)
