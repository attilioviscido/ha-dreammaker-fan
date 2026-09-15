"""Select platform for Dream Maker Fan: oscillation angle."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ANGLE_OPTIONS, DOMAIN, SIGNAL_NEW_DEVICE
from .entity import DreamMakerEntity
from .server import DreamMakerDevice, DreamMakerServer


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    server: DreamMakerServer = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _new_device(device: DreamMakerDevice):
        async_add_entities([DreamMakerAngleSelect(device)])

    for device in server.devices.values():
        _new_device(device)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{SIGNAL_NEW_DEVICE}_{entry.entry_id}", _new_device)
    )


class DreamMakerAngleSelect(DreamMakerEntity, SelectEntity):
    _attr_name = "Angolo oscillazione"
    _attr_icon = "mdi:angle-acute"
    _attr_options = ANGLE_OPTIONS

    def __init__(self, device: DreamMakerDevice):
        super().__init__(device, "roll_angle")

    @property
    def current_option(self) -> str | None:
        angle = self._device.state.get("roll_angle")
        return str(angle) if angle is not None else None

    async def async_select_option(self, option: str) -> None:
        await self._device.async_send_command({"roll_angle": int(option)})
