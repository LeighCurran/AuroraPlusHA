"""The auroraplus sensor integration."""

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME
  )

DOMAIN = "auroraplus"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Exclusive(CONF_USERNAME, CONF_PASSWORD): cv.string,

        vol.Required(CONF_PASSWORD): cv.string

    }, extra=vol.ALLOW_EXTRA),
}, extra=vol.ALLOW_EXTRA)

def setup(hass, config):
    """Set up a skeleton component."""
    # States are in the format DOMAIN.OBJECT_ID.
    hass.states.set('auroraplus.auroraplus', 'Works!')

    # Return boolean to indicate that initialization was successfully.
    return True