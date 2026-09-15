"""Config flow for Dream Maker Fan. Singolo entry, nessun parametro obbligatorio."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_PORT, DOMAIN


class DreamMakerFanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dream Maker Fan."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        # Una sola istanza: il server ascolta su una porta fissa condivisa da
        # tutti i ventilatori (identificati poi per IP).
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Dream Maker Fan", data=user_input)

        schema = vol.Schema({vol.Optional("port", default=DEFAULT_PORT): int})
        return self.async_show_form(step_id="user", data_schema=schema)
