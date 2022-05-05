"""Aurora+ sensor platform."""
import logging
from typing import Callable, Optional

from .const import CONF_ROUNDING, DOMAIN, SENSOR_ESTIMATEDBALANCE, SENSOR_DOLLARVALUEUSAGE, SENSOR_KILOWATTHOURUSAGE, POSSIBLE_MONITORED

import voluptuous as vol
import auroraplus

from homeassistant import config_entries, core

from homeassistant.components.sensor import (
    STATE_CLASS_TOTAL,
    STATE_CLASS_MEASUREMENT,
    SensorEntity
)

from homeassistant.const import (
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    CURRENCY_DOLLAR,
    ENERGY_KILO_WATT_HOUR,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_ENERGY,
)

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)

_LOGGER = logging.getLogger(__name__)

def connect(username, password):

    try:
        aurora = auroraplus.api(username, password)
        raised = True
        return aurora
    except Exception as e:
        _LOGGER.error("Failed to connect during setup: %s", e)

    if not raised:
        exit()

async def async_setup_entry(hass: core.HomeAssistant,config_entry: config_entries.ConfigEntry,async_add_entities):

    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    # Update our config
    if config_entry.options:
        config.update(config_entry.options)

    """Set up the Aurora+ platform for sensors."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    name = config[CONF_NAME]
    rounding = config[CONF_ROUNDING]

    aurora = await hass.async_add_executor_job(connect, username, password)

    sensors = []
    for sensor in POSSIBLE_MONITORED:
        _LOGGER.debug("Adding sensor from UI: %s", sensor)
        sensors.append(AuroraSensor(username, password, sensor, name, aurora, rounding))

    if sensors:
        async_add_entities(sensors, update_before_add=True)


async def async_setup_platform(hass: HomeAssistantType,config: ConfigType,async_add_entities: Callable,discovery_info: Optional[DiscoveryInfoType] = None,) -> None:
    """Set up the sensor platform from configuration.yaml."""
    """Set up the Aurora+ platform for sensors."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    name = config[CONF_NAME]
    rounding = config[CONF_ROUNDING]

    aurora = await hass.async_add_executor_job(connect, username, password)

    sensors = []
    for sensor in POSSIBLE_MONITORED:
        _LOGGER.debug("Adding sensor from configuration.yaml: %s", sensor)
        sensors.append(AuroraSensor(username, password, sensor, name, aurora, rounding))

    if sensors:
        async_add_entities(sensors, update_before_add=True)


class AuroraSensor(SensorEntity):
    """Representation of a Aurora+ sensor."""

    def __init__(self, username, password, sensor, name, aurora, rounding):
        """Initialize the Aurora+ sensor."""
        self._username = username
        self._password = password
        self._name = name + ' ' + sensor
        self._sensor = sensor
        self._unit_of_measurement = None
        self._state = None
        self._session = aurora
        self._uniqueid = self._name
        self._rounding = rounding

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        if self._sensor == SENSOR_ESTIMATEDBALANCE:
            return STATE_CLASS_MEASUREMENT
        else:
            return STATE_CLASS_TOTAL

    @property
    def device_class(self):
        """Return device class fo the sensor."""
        if self._sensor == SENSOR_KILOWATTHOURUSAGE:
            return DEVICE_CLASS_ENERGY
        else:
            return DEVICE_CLASS_MONETARY

    @property
    def unique_id(self):
        """Return the unique_id of the sensor."""
        return self._uniqueid

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
            _LOGGER.debug("Updating sensor: %s", self._sensor)
            self._session.getcurrent()
            if self._sensor == SENSOR_KILOWATTHOURUSAGE or self._sensor == SENSOR_DOLLARVALUEUSAGE:     
                self._session.getsummary()
            self._data = self._session
        except Exception as err:
            _LOGGER.error("Updating Aurora+ failed: %s", err)

        """Collect updated data from Aurora+ API."""
        if self._sensor == SENSOR_ESTIMATEDBALANCE:
            self._state = round(float(self._session.EstimatedBalance),self._rounding)
        elif self._sensor == SENSOR_DOLLARVALUEUSAGE:       
            self._state = round(self._session.DollarValueUsage['Total'],self._rounding)
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:       
            self._state = round(self._session.KilowattHourUsage['Total'],self._rounding)
        else:
            _LOGGER.error("Unknown sensor type found") 