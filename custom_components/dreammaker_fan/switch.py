"""Switch platform for Dream Maker Fan: sound, LED light, child lock."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_NEW_DEVICE
from .entity import DreamMakerEntity
from .server import DreamMakerDevice, DreamMakerServer

SWITCH_DEFINITIONS = [
    ("sound", "Suono tasti", "mdi:volume-high"),
    ("light", "Luce LED", "mdi:led-outline"),
    ("child_lock", "Blocco bambini", "mdi:lock"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    server: DreamMakerServer = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _new_device(device: DreamMakerDevice):
        async_add_entities(
            [DreamMakerSwitch(device, key, name, icon) for key, name, icon in SWITCH_DEFINITIONS]
        )

    for device in server.devices.values():
        _new_device(device)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{SIGNAL_NEW_DEVICE}_{entry.entry_id}", _new_device)
    )


class DreamMakerSwitch(DreamMakerEntity, SwitchEntity):
    def __init__(self, device: DreamMakerDevice, key: str, name: str, icon: str):
        super().__init__(device, key)
        self._attr_name = name
        self._attr_icon = icon

    @property
    def is_on(self) -> bool | None:
        value = self._device.state.get(self._key)
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.async_send_command({self._key: 1})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.async_send_command({self._key: 0})
