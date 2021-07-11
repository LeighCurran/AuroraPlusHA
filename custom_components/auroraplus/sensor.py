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
    CONF_MONITORED_CONDITIONS,
    CURRENCY_DOLLAR,
    ENERGY_KILO_WATT_HOUR,
    CONF_SCAN_INTERVAL,
    TIME_DAYS
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SENSOR_ESTIMATEDBALANCE = 'EstimatedBalance'
SENSOR_USAGEDAYSREMAINING = 'UsageDaysRemaining'
SENSOR_AVERAGEDAILYUSAGE = 'AverageDailyUsage'
SENSOR_AMOUNTOWED = 'AmountOwed'
SENSOR_ACTUALBALANCE = 'ActualBalance'
SENSOR_UNBILLEDAMOUNT = 'UnbilledAmount'
SENSOR_BILLTOTALAMOUNT = 'BillTotalAmount'
SENSOR_BILLOVERDUEAMOUNT  = 'BillOverDueAmount'
SENSOR_DOLLARVALUEUSAGE =  'DollarValueUsage'
SENSOR_KILOWATTHOURUSAGE = 'KilowattHourUsage'

POSSIBLE_MONITORED = [ SENSOR_ESTIMATEDBALANCE, SENSOR_USAGEDAYSREMAINING, SENSOR_AVERAGEDAILYUSAGE, SENSOR_AMOUNTOWED,
                        SENSOR_ACTUALBALANCE, SENSOR_UNBILLEDAMOUNT, SENSOR_BILLTOTALAMOUNT, SENSOR_BILLOVERDUEAMOUNT,
                        SENSOR_DOLLARVALUEUSAGE, SENSOR_KILOWATTHOURUSAGE]

DEFAULT_MONITORED = POSSIBLE_MONITORED

DEFAULT_NAME = 'AuroraPlus'

DEFAULT_SCAN_INTERVAL = timedelta(hours=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
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
        auroraplus.api(username, password)
    except OSError as err:
        _LOGGER.error("Connection to Aurora+ failed: %s", err)
    
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
        self._unit_of_measurement = None
        self._attributes = {}
        self._data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:
            return ENERGY_KILO_WATT_HOUR
        else:
            return CURRENCY_DOLLAR

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        if self._sensor == SENSOR_DOLLARVALUEUSAGE:   
            return self._data.DollarValueUsage
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:   
            return self._data.KilowattHourUsage

    def update(self):
        try:
            AuroraPlus = auroraplus.api(self._username , self._password)
            AuroraPlus.getcurrent()
            if self._sensor == SENSOR_KILOWATTHOURUSAGE or self._sensor == SENSOR_DOLLARVALUEUSAGE:     
                AuroraPlus.getsummary()
            self._data = AuroraPlus
        except OSError as err:
            _LOGGER.error("Updating Aurora+ failed: %s", err)

        """Collect updated data from Aurora+ API."""
        if self._sensor == SENSOR_ESTIMATEDBALANCE:
            self._state = self._data.EstimatedBalance
        elif self._sensor == SENSOR_USAGEDAYSREMAINING:    
            self._state = self._data.UsageDaysRemaining
        elif self._sensor == SENSOR_AVERAGEDAILYUSAGE:
            self._state = self._data.AverageDailyUsage
        elif self._sensor == SENSOR_AMOUNTOWED:    
            self._state = self._data.AmountOwed
        elif self._sensor == SENSOR_ACTUALBALANCE:    
            self._state = self._data.ActualBalance
        elif self._sensor == SENSOR_UNBILLEDAMOUNT:    
            self._state = self._data.UnbilledAmount
        elif self._sensor == SENSOR_BILLTOTALAMOUNT: 
            self._state = self._data.BillTotalAmount
        elif self._sensor == SENSOR_BILLOVERDUEAMOUNT:       
            self._state = self._data.BillOverDueAmount
        elif self._sensor == SENSOR_DOLLARVALUEUSAGE:       
            self._state = self._data.DollarValueUsage['Total']
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:       
            self._state = self._data.KilowattHourUsage['Total'] 
        else:
            _LOGGER.error("Unknown sensor type found")