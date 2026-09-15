"""Fan platform for Dream Maker Fan."""
from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODE_MAP, MODE_MAP_REVERSE, SIGNAL_NEW_DEVICE
from .entity import DreamMakerEntity
from .server import DreamMakerDevice, DreamMakerServer


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    server: DreamMakerServer = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _new_device(device: DreamMakerDevice):
        async_add_entities([DreamMakerFan(device)])

    for device in server.devices.values():
        _new_device(device)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{SIGNAL_NEW_DEVICE}_{entry.entry_id}", _new_device)
    )


class DreamMakerFan(DreamMakerEntity, FanEntity):
    """Rappresenta il ventilatore stesso: accensione, velocità, oscillazione, modalità."""

    _attr_preset_modes = list(MODE_MAP_REVERSE.keys())
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = 100

    def __init__(self, device: DreamMakerDevice):
        super().__init__(device, "fan")
        self._attr_name = None  # entity carries the device name (has_entity_name)

    @property
    def is_on(self) -> bool | None:
        power = self._device.state.get("power")
        return bool(power) if power is not None else None

    @property
    def percentage(self) -> int | None:
        return self._device.state.get("speed")

    @property
    def oscillating(self) -> bool | None:
        roll_enable = self._device.state.get("roll_enable")
        return bool(roll_enable) if roll_enable is not None else None

    @property
    def preset_mode(self) -> str | None:
        mode = self._device.state.get("mode")
        return MODE_MAP.get(mode) if mode is not None else None

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs: Any) -> None:
        await self._device.async_send_command({"power": 1})
        if percentage is not None:
            await self.async_set_percentage(percentage)
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.async_send_command({"power": 0})

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        await self._device.async_send_command({"speed": max(1, min(100, percentage))})

    async def async_oscillate(self, oscillating: bool) -> None:
        await self._device.async_send_command({"roll_enable": 1 if oscillating else 0})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._device.async_send_command({"mode": MODE_MAP_REVERSE[preset_mode]})
