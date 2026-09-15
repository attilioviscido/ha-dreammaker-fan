"""Number platform for Dream Maker Fan: auto-off timer (power_delay)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_NEW_DEVICE
from .entity import DreamMakerEntity
from .server import DreamMakerDevice, DreamMakerServer


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    server: DreamMakerServer = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _new_device(device: DreamMakerDevice):
        async_add_entities([DreamMakerPowerDelay(device)])

    for device in server.devices.values():
        _new_device(device)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{SIGNAL_NEW_DEVICE}_{entry.entry_id}", _new_device)
    )


class DreamMakerPowerDelay(DreamMakerEntity, NumberEntity):
    _attr_name = "Spegnimento automatico"
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = 480
    _attr_native_step = 10
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX

    def __init__(self, device: DreamMakerDevice):
        super().__init__(device, "power_delay")

    @property
    def native_value(self) -> float | None:
        return self._device.state.get("power_delay")

    async def async_set_native_value(self, value: float) -> None:
        await self._device.async_send_command({"power_delay": int(value)})
