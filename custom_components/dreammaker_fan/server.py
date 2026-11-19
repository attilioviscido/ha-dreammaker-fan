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
from .parser import JsonStreamParser

_LOGGER = logging.getLogger(__name__)

# Seconds to wait for open fan connections to close when the entry unloads.
CLOSE_TIMEOUT = 5
# Bytes requested per read from the fan socket.
READ_SIZE = 4096

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
        _LOGGER.debug("Sending command to %s: %s", self.device_ip, command_data)
        self._writer.write(payload)
        await self._writer.drain()


class DreamMakerServer:
    """Owns the asyncio TCP server and the set of known devices."""

    def __init__(self, hass: HomeAssistant, entry_id: str, port: int = DEFAULT_PORT):
        self.hass = hass
        self.entry_id = entry_id
        self.port = port
        self.devices: dict[str, DreamMakerDevice] = {}
        # Every open fan socket, so async_stop() can close all of them, also a
        # stale one that a reconnecting fan left behind.
        self._connections: set[asyncio.StreamWriter] = set()
        self._server: asyncio.AbstractServer | None = None

    async def async_start(self):
        self._server = await asyncio.start_server(self._handle_client, "0.0.0.0", self.port)
        _LOGGER.info("Dream Maker fan server listening on port %s", self.port)

    async def async_stop(self):
        if self._server is not None:
            self._server.close()
            # Close the open fan connections as well. Since Python 3.12
            # wait_closed() also waits for active connections, so without this
            # the config entry hangs in "unload in progress" while a fan is
            # connected.
            for writer in list(self._connections):
                try:
                    writer.close()
                except Exception:  # noqa: BLE001
                    pass
            try:
                await asyncio.wait_for(self._server.wait_closed(), timeout=CLOSE_TIMEOUT)
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout waiting for the Dream Maker fan server to close")
            self._server = None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        device_ip = addr[0] if addr else "unknown"
        _LOGGER.info("Fan %s connected", device_ip)

        self._connections.add(writer)
        device = self.devices.get(device_ip)
        is_new = device is None
        if is_new:
            device = DreamMakerDevice(self.hass, device_ip, writer)
            self.devices[device_ip] = device
        else:
            # Reconnected on a new socket (e.g. after a power cut or a
            # re-pairing). The fan does not always close the old one, so close
            # it here; its handler then ends on EOF.
            old_writer = device._writer
            device._writer = writer
            device.available = True
            if old_writer is not writer and not old_writer.is_closing():
                _LOGGER.debug("Closing previous connection of fan %s", device_ip)
                old_writer.close()
                try:
                    await asyncio.wait_for(old_writer.wait_closed(), timeout=1)
                except Exception:  # noqa: BLE001
                    pass

        # Parser state belongs to this connection only, so it disappears with it.
        parser = JsonStreamParser()

        try:
            authenticated = await self._authenticate(reader, writer, device, parser)
            if not authenticated:
                return

            if is_new:
                _LOGGER.debug("Fan %s authenticated, creating device", device_ip)
                async_dispatcher_send(self.hass, f"{SIGNAL_NEW_DEVICE}_{self.entry_id}", device)

            while not reader.at_eof():
                message = await self._read_message(reader, parser)
                if not message:
                    continue
                await self._handle_message(writer, device, message)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError) as err:
            _LOGGER.info("Fan %s disconnected: %s", device_ip, err)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error handling fan %s", device_ip)
        finally:
            self._connections.discard(writer)
            # A replaced (old) connection must not mark the fan unavailable
            # while its new connection is active.
            if device._writer is writer:
                device.mark_unavailable()
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    async def _authenticate(
        self, reader, writer, device: DreamMakerDevice, parser: JsonStreamParser
    ) -> bool:
        while not reader.at_eof():
            message = await self._read_message(reader, parser)
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
                # As upstream dmiot2mqtt: use the serial number as device_id, so
                # the fan gets a unique id instead of the shared all-zero one.
                serial = (message.get("data") or {}).get("sn")
                if serial:
                    response["data"]["device_id"] = str(serial)
                await self._send(writer, response)
            elif message.get("action") == 1 and message.get("resource_id") == 2001:
                _LOGGER.debug("Auth handshake from %s", device.device_ip)
                await self._ack(writer, message)
                return True
        return False

    async def _handle_message(self, writer, device: DreamMakerDevice, message: dict):
        _LOGGER.debug(
            "Message from %s: action=%s resource=%s data=%s",
            device.device_ip,
            message.get("action"),
            message.get("resource_id"),
            message.get("data"),
        )
        await self._ack(writer, message)
        resource_id = message.get("resource_id")
        data = message.get("data", {})
        if resource_id == RESOURCE_STATUS:
            device.update_heartbeat(data)
        elif resource_id == RESOURCE_STATE:
            device.update_state(data)

    @staticmethod
    async def _read_message(reader: asyncio.StreamReader, parser: JsonStreamParser) -> dict:
        """Return the next complete message of this connection, {} on EOF."""
        while not parser.pending:
            data = await reader.read(READ_SIZE)
            if not data:
                return {}
            _LOGGER.debug("Received %s bytes: %r", len(data), data)
            parser.feed(data)
        return parser.pending.popleft()

    @staticmethod
    async def _send(writer: asyncio.StreamWriter, data: dict):
        _LOGGER.debug(
            "Sending action=%s resource=%s data=%s",
            data.get("action"),
            data.get("resource_id"),
            data.get("data"),
        )
        writer.write(json.dumps(data).encode())
        await writer.drain()

    async def _ack(self, writer: asyncio.StreamWriter, message: dict):
        response = copy.copy(REPLY_TEMPLATE)
        response["resource_id"] = message.get("resource_id", 0)
        await self._send(writer, response)
