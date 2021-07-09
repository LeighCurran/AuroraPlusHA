"""Support for Aurora+"""
from datetime import timedelta
import logging

import auroraplus
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_NAME,
    CURRENCY_DOLLAR
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=6)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Aurora+ platform for sensors."""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        api = auroraplus.api(username, password)
        add_entities([AuroraAccountSensor(username, password)], True)
    except OSError as err:
        _LOGGER.error("Connection to Aurora+ failed: %s", err)
        return False
    

class AuroraAccountSensor(SensorEntity):
    """Representation of a Aurora+ sensor."""

    def __init__(self, username, password):
        """Initialize the Aurora+ sensor."""
        self.username = username
        self.password = password

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Auroraplus UsageDaysRemaining'

    #@property
    #def unique_id(self):
        """Return unique ID for the sensor."""
    #    return 'test'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:power-socket-au"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return CURRENCY_DOLLAR

    def update(self):
        """Collect updated data from Aurora+ API."""
        try:
            AuroraPlus = auroraplus.api(self.username , self.password)
            AuroraPlus.getcurrent()
            self._state = AuroraPlus.UsageDaysRemaining
        except OSError as err:
            _LOGGER.error("Connection to Aurora+ failed: %s", err)
        return False