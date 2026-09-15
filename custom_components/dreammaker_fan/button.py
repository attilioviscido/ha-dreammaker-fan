"""Button platform for Dream Maker Fan: manual one-step rotation left/right."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_NEW_DEVICE
from .entity import DreamMakerEntity
from .server import DreamMakerDevice, DreamMakerServer

BUTTON_DEFINITIONS = [
    ("roll_control_left", "Ruota a sinistra", "mdi:rotate-left", 1),
    ("roll_control_right", "Ruota a destra", "mdi:rotate-right", 2),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    server: DreamMakerServer = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _new_device(device: DreamMakerDevice):
        async_add_entities(
            [DreamMakerButton(device, key, name, icon, value) for key, name, icon, value in BUTTON_DEFINITIONS]
        )

    for device in server.devices.values():
        _new_device(device)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{SIGNAL_NEW_DEVICE}_{entry.entry_id}", _new_device)
    )


class DreamMakerButton(DreamMakerEntity, ButtonEntity):
    def __init__(self, device: DreamMakerDevice, key: str, name: str, icon: str, roll_control_value: int):
        super().__init__(device, key)
        self._attr_name = name
        self._attr_icon = icon
        self._value = roll_control_value

    async def async_press(self) -> None:
        await self._device.async_send_command({"roll_control": self._value})
