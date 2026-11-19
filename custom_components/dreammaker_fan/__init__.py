"""The Dream Maker Fan integration.

Intercetta la connessione dei ventilatori Dream Maker (DM-FAN01, DM-FAN02-W)
fingendosi il loro server cloud (cloud1.dm-maker.com), e crea le entità
direttamente in Home Assistant. Richiede un redirect DNS locale di
cloud1.dm-maker.com verso l'IP di questo host - vedi README.md.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DEFAULT_PORT, DOMAIN
from .server import DreamMakerServer

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["fan", "sensor", "switch", "select", "number", "button", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    port = entry.data.get("port", DEFAULT_PORT)
    _LOGGER.debug("Setting up entry %s, starting server on port %s", entry.entry_id, port)

    try:
        server = DreamMakerServer(hass, entry.entry_id, port=port)
        await server.async_start()
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Could not start Dream Maker fan server")
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = server

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("Entry %s set up", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        server: DreamMakerServer = hass.data[DOMAIN].pop(entry.entry_id)
        await server.async_stop()
    return unload_ok
