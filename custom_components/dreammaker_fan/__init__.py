"""The Dream Maker Fan integration.

Intercetta la connessione dei ventilatori Dream Maker (DM-FAN01, DM-FAN02-W)
fingendosi il loro server cloud (cloud1.dm-maker.com), e crea le entità
direttamente in Home Assistant. Richiede un redirect DNS locale di
cloud1.dm-maker.com verso l'IP di questo host - vedi README.md.
"""
from __future__ import annotations

import logging
import traceback

print("[dreammaker_fan] __init__.py module import STARTED", flush=True)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DEFAULT_PORT, DOMAIN

try:
    from .server import DreamMakerServer
except Exception:  # noqa: BLE001
    print("[dreammaker_fan] EXCEPTION importing .server:", flush=True)
    traceback.print_exc()
    raise

print("[dreammaker_fan] __init__.py module import COMPLETED OK", flush=True)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["fan", "sensor", "switch", "select", "number", "button", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # print() va dritto sullo stdout del container: compare SEMPRE in
    # "ha core logs", indipendentemente da qualunque configurazione di
    # logging. Usato qui solo per diagnosticare il problema di avvio.
    print(f"[dreammaker_fan] async_setup_entry CALLED, entry_id={entry.entry_id}", flush=True)

    try:
        port = entry.data.get("port", DEFAULT_PORT)
        print(f"[dreammaker_fan] starting server on port {port}", flush=True)
        server = DreamMakerServer(hass, entry.entry_id, port=port)
        await server.async_start()
        print(f"[dreammaker_fan] server.async_start() completed OK", flush=True)
    except Exception:  # noqa: BLE001
        print("[dreammaker_fan] EXCEPTION during setup:", flush=True)
        traceback.print_exc()
        _LOGGER.exception("Could not start Dream Maker fan server")
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = server

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:  # noqa: BLE001
        print("[dreammaker_fan] EXCEPTION during platform forward:", flush=True)
        traceback.print_exc()
        raise

    print("[dreammaker_fan] async_setup_entry finished, returning True", flush=True)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        server: DreamMakerServer = hass.data[DOMAIN].pop(entry.entry_id)
        await server.async_stop()
    return unload_ok
