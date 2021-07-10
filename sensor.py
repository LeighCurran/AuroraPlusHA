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
    CONF_TYPE,
    CONF_MONITORED_CONDITIONS,
    CURRENCY_DOLLAR,
    TIME_DAYS
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=6)

SENSOR_ESTIMATEDBALANCE = 'EstimatedBalance'
SENSOR_USAGEDAYSREMAINING = 'UsageDaysRemaining'
SENSOR_AVERAGEDAILYUSAGE = 'AverageDailyUsaged'
SENSOR_AMOUNTOWED = 'AmountOwed'
SENSOR_ACTUALBALANCE = 'ActualBalance'
SENSOR_UNBILLEDAMOUNT = 'UnbilledAmount'
SENSOR_BILLTOTALAMOUNT = 'BillTotalAmount'
SENSOR_BILLOVERDUEAMOUNT  = 'BillOverDueAmount'

POSSIBLE_MONITORED = [ SENSOR_ESTIMATEDBALANCE, SENSOR_USAGEDAYSREMAINING, SENSOR_AVERAGEDAILYUSAGE, SENSOR_AMOUNTOWED,
                        SENSOR_ACTUALBALANCE, SENSOR_UNBILLEDAMOUNT, SENSOR_BILLTOTALAMOUNT, SENSOR_BILLOVERDUEAMOUNT ]
DEFAULT_MONITORED = POSSIBLE_MONITORED
DEFAULT_NAME = 'AuroraPlus'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=DEFAULT_MONITORED):
            vol.All(cv.ensure_list, [vol.In(POSSIBLE_MONITORED)])
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Aurora+ platform for sensors."""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    name = config.get(CONF_NAME)

    try:
        api = auroraplus.api(username, password)
    except OSError as err:
        _LOGGER.error("Connection to Aurora+ failed: %s", err)
        return False

    for sensor in config.get(CONF_MONITORED_CONDITIONS):
        add_entities([AuroraAccountSensor(username, password, sensor, name)], True)


class AuroraAccountSensor(SensorEntity):
    """Representation of a Aurora+ sensor."""

    def __init__(self, username, password, sensor, name):
        """Initialize the Aurora+ sensor."""
        self._username = username
        self._password = password
        self._name = name + ' ' + sensor
        self._sensor = sensor
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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

        if self._sensor == SENSOR_USAGEDAYSREMAINING:   
            return TIME_DAYS
        else:
            return CURRENCY_DOLLAR


    def update(self):
        """Collect updated data from Aurora+ API."""
        try:
            AuroraPlus = auroraplus.api(self._username , self._password)
            AuroraPlus.getcurrent()

            if self._sensor == SENSOR_ESTIMATEDBALANCE:
                self._state = AuroraPlus.EstimatedBalance

            elif self._sensor == SENSOR_USAGEDAYSREMAINING:    
                self._state = AuroraPlus.UsageDaysRemaining

            elif self._sensor == SENSOR_AVERAGEDAILYUSAGE:  
                #Need to fix spelling mistake here  
                self._state = AuroraPlus.AverageDailyUsaged

            elif self._sensor == SENSOR_AMOUNTOWED:    
                self._state = AuroraPlus.AmountOwed

            elif self._sensor == SENSOR_ACTUALBALANCE:    
                self._state = AuroraPlus.ActualBalance

            elif self._sensor == SENSOR_UNBILLEDAMOUNT:    
                self._state = AuroraPlus.UnbilledAmount

            elif self._sensor == SENSOR_BILLTOTALAMOUNT: 
                self._state = AuroraPlus.BillTotalAmount

            elif self._sensor == SENSOR_BILLOVERDUEAMOUNT:       
                self._state = AuroraPlus.BillOverDueAmount
            else:
                _LOGGER.error("Unknown sensor type found")


        except OSError as err:
            _LOGGER.error("Connection to Aurora+ failed: %s", err)
        return False