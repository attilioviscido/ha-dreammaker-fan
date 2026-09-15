"""Base entity for Dream Maker Fan devices."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, MANUFACTURER
from .server import DreamMakerDevice


class DreamMakerEntity(Entity):
    """Common base: device info, availability, push updates via listener."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: DreamMakerDevice, description_key: str):
        self._device = device
        self._key = description_key
        self._attr_unique_id = f"{device.unique_id}_{description_key}"

    @property
    def available(self) -> bool:
        return self._device.available

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.device_ip)},
            manufacturer=MANUFACTURER,
            model="DM-FAN02-W",
            name=f"Ventilatore Dream Maker ({self._device.device_ip})",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_listener(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()
