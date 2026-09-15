"""Binary sensor platform for Dream Maker Fan: device/use exceptions."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_NEW_DEVICE
from .entity import DreamMakerEntity
from .server import DreamMakerDevice, DreamMakerServer

DEFINITIONS = [
    ("deviceException", "Anomalia dispositivo"),
    ("useException", "Anomalia utilizzo"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    server: DreamMakerServer = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _new_device(device: DreamMakerDevice):
        async_add_entities(
            [DreamMakerProblemSensor(device, key, name) for key, name in DEFINITIONS]
        )

    for device in server.devices.values():
        _new_device(device)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{SIGNAL_NEW_DEVICE}_{entry.entry_id}", _new_device)
    )


class DreamMakerProblemSensor(DreamMakerEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device: DreamMakerDevice, key: str, name: str):
        super().__init__(device, key)
        self._attr_name = name

    @property
    def is_on(self) -> bool | None:
        value = self._device.state.get(self._key)
        return bool(value) if value is not None else None
