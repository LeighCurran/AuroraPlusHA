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
    CONF_SCAN_INTERVAL
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SENSOR_ESTIMATEDBALANCE = 'EstimatedBalance'
SENSOR_DOLLARVALUEUSAGE =  'DollarValueUsage'
SENSOR_KILOWATTHOURUSAGE = 'KilowattHourUsage'

POSSIBLE_MONITORED = [ SENSOR_ESTIMATEDBALANCE, SENSOR_DOLLARVALUEUSAGE, SENSOR_KILOWATTHOURUSAGE]

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
        AuroraPlus = auroraplus.api()
        AuroraPlus.auth(username, password)
    except OSError as err:
        _LOGGER.error("Connection to Aurora+ failed: %s", err)

    for sensor in config.get(CONF_MONITORED_CONDITIONS):
        add_entities([AuroraSensor(username, password, sensor, name, AuroraPlus)], True)


class AuroraSensor(SensorEntity):
    """Representation of a Aurora+ sensor."""

    def __init__(self, username, password, sensor, name, auroraplus):
        """Initialize the Aurora+ sensor."""
        self._username = username
        self._password = password
        self._name = name + ' ' + sensor
        self._sensor = sensor
        self._state = None
        self._unit_of_measurement = None
        self._attributes = {}
        self._session = auroraplus

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
        if self._sensor == SENSOR_KILOWATTHOURUSAGE:
            return ENERGY_KILO_WATT_HOUR
        else:
            return CURRENCY_DOLLAR

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        if self._sensor == SENSOR_DOLLARVALUEUSAGE:   
            return self._session.DollarValueUsage
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:   
            return self._session.KilowattHourUsage
        elif self._sensor == SENSOR_ESTIMATEDBALANCE:   
            attributes = {}
            attributes['Amount Owed'] = self._session.AmountOwed
            attributes['Average Daily Usage'] = self._session.AverageDailyUsage
            attributes['Usage Days Remaining'] = self._session.UsageDaysRemaining
            attributes['Actual Balance'] = self._session.ActualBalance
            attributes['Unbilled Amount'] = self._session.UnbilledAmount
            attributes['Bill Total Amount'] = self._session.BillTotalAmount
            attributes['Number Of Unpaid Bills'] = self._session.NumberOfUnpaidBills
            attributes['Bill Overdue Amount'] = self._session.BillOverDueAmount
            return attributes

    def update(self):
        try:
            self._session.getcurrent()
            if self._sensor == SENSOR_KILOWATTHOURUSAGE or self._sensor == SENSOR_DOLLARVALUEUSAGE:     
                self._session.getsummary()
            self._data = self._session
            self._data = self._session.close()
        except OSError as err:
            _LOGGER.error("Updating Aurora+ failed: %s", err)

        """Collect updated data from Aurora+ API."""
        if self._sensor == SENSOR_ESTIMATEDBALANCE:
            self._state = self._session.EstimatedBalance
        elif self._sensor == SENSOR_DOLLARVALUEUSAGE:       
            self._state = round(self._session.DollarValueUsage['Total'],2)
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:       
            self._state = round(self._session.KilowattHourUsage['Total'],2)
        else:
            _LOGGER.error("Unknown sensor type found")