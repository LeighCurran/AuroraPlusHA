from typing import Any, Dict, Optional
from datetime import timedelta
import auroraplus

import logging
_LOGGER = logging.getLogger(__name__)

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

#DEFAULT_SCAN_INTERVAL = timedelta(hours=1)
DEFAULT_SCAN_INTERVAL = 1

from .const import DOMAIN, CONF_ROUNDING, DEFAULT_NAME, DEFAULT_ROUNDING

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str, 
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Optional(CONF_ROUNDING, default=DEFAULT_ROUNDING): vol.Coerce(int),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.Coerce(int)
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Aurora Custom config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    #data: Optional[Dict[str, Any]]

    def validate_input(self):
       
        raised = False       
        try:
            auroraplus.api(self.username, self.password)
            raised = True
        except Exception as e:
            _LOGGER.debug(e)

        if not raised:
            exit()

    async def async_step_user(self, user_input = None):
        """Invoked when a user initiates a flow via the user interface."""
        
        errors = {}
        if user_input is not None:
            try:
                self.username = user_input[CONF_USERNAME]
                self.password = user_input[CONF_PASSWORD]
                name = user_input[CONF_NAME]
                await self.hass.async_add_executor_job(self.validate_input)
                return self.async_create_entry(title=f"{name}", data=user_input)
            #except CannotConnect:
            #    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME,default=self.config_entry.options.get(CONF_NAME, DEFAULT_NAME),): str,
                    vol.Optional(CONF_ROUNDING,default=self.config_entry.options.get(CONF_ROUNDING,DEFAULT_ROUNDING),): int,
                    vol.Optional(CONF_SCAN_INTERVAL,default=self.config_entry.options.get(CONF_SCAN_INTERVAL,DEFAULT_SCAN_INTERVAL),): int
                }
            ),
        )