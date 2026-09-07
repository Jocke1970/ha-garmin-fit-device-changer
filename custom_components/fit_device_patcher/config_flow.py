"""Config flow for FIT Device Patcher."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN, NAME


class FitDevicePatcherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create the single FIT Device Patcher config entry."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle installation from Settings > Devices & services."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )
