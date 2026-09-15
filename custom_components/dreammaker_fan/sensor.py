"""Sensor platform for Dream Maker Fan: temperature, humidity, wifi signal, source."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfTemperature
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
        async_add_entities(
            [
                DreamMakerTemperatureSensor(device),
                DreamMakerHumiditySensor(device),
                DreamMakerWifiSignalSensor(device),
                DreamMakerSourceSensor(device),
            ]
        )

    for device in server.devices.values():
        _new_device(device)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{SIGNAL_NEW_DEVICE}_{entry.entry_id}", _new_device)
    )


class DreamMakerTemperatureSensor(DreamMakerEntity, SensorEntity):
    _attr_name = "Temperatura"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, device: DreamMakerDevice):
        super().__init__(device, "temperature")

    @property
    def native_value(self):
        return self._device.state.get("temperature")


class DreamMakerHumiditySensor(DreamMakerEntity, SensorEntity):
    _attr_name = "Umidità"
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, device: DreamMakerDevice):
        super().__init__(device, "humidity")

    @property
    def native_value(self):
        return self._device.state.get("humidity")


class DreamMakerWifiSignalSensor(DreamMakerEntity, SensorEntity):
    _attr_name = "Segnale WiFi"
    _attr_icon = "mdi:wifi"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device: DreamMakerDevice):
        super().__init__(device, "wifi_signal")

    @property
    def native_value(self):
        return self._device.heartbeat.get("signal")


class DreamMakerSourceSensor(DreamMakerEntity, SensorEntity):
    _attr_name = "Sorgente comando"
    _attr_icon = "mdi:remote"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device: DreamMakerDevice):
        super().__init__(device, "source")

    @property
    def native_value(self):
        return self._device.state.get("source")
