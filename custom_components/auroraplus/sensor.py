"""Support for Aurora+"""
import homeassistant.helpers.config_validation as cv
import datetime
import logging

import auroraplus
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_TOTAL,
    SensorEntity
)

from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_NAME,
    CONF_MONITORED_CONDITIONS,
    CURRENCY_DOLLAR,
    ENERGY_KILO_WATT_HOUR,
    CONF_SCAN_INTERVAL,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_ENERGY,
)

from homeassistant.util import Throttle

CONF_ROUNDING = "rounding"


_LOGGER = logging.getLogger(__name__)

SENSOR_ESTIMATEDBALANCE = 'Estimated Balance'
SENSOR_DOLLARVALUEUSAGE = 'Dollar Value Usage'
SENSOR_KILOWATTHOURUSAGE = 'Kilowatt Hour Usage'
SENSOR_KILOWATTHOURUSAGETARIFF = 'Kilowatt Hour Usage Tariff '

SENSORS_MONETARY = [
    SENSOR_ESTIMATEDBALANCE,
    SENSOR_DOLLARVALUEUSAGE,
]

SENSORS_ENERGY = [
    SENSOR_KILOWATTHOURUSAGE,
    SENSOR_KILOWATTHOURUSAGETARIFF + 'T31',
    SENSOR_KILOWATTHOURUSAGETARIFF + 'T41',
    SENSOR_KILOWATTHOURUSAGETARIFF + 'T61',
    SENSOR_KILOWATTHOURUSAGETARIFF + 'T62',
    SENSOR_KILOWATTHOURUSAGETARIFF + 'T93PEAK',
    SENSOR_KILOWATTHOURUSAGETARIFF + 'T93OFFPEAK',
    SENSOR_KILOWATTHOURUSAGETARIFF + 'T140',
]

POSSIBLE_MONITORED = SENSORS_MONETARY + SENSORS_ENERGY

DEFAULT_MONITORED = POSSIBLE_MONITORED

DEFAULT_NAME = 'Aurora+'
DEFAULT_ROUNDING = 2

DEFAULT_SCAN_INTERVAL = datetime.timedelta(hours=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ROUNDING, default=DEFAULT_ROUNDING): vol.Coerce(int),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=DEFAULT_MONITORED):
            vol.All(cv.ensure_list, [vol.In(POSSIBLE_MONITORED)])
    }
)


async def async_setup_platform(hass, config,
                               async_add_entities,
                               discovery_info=None):
    """Set up the Aurora+ platform for sensors."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    name = config.get(CONF_NAME)
    rounding = config.get(CONF_ROUNDING)

    try:
        def aurora_init():
            return auroraplus.api(username, password)
        AuroraPlus = await hass.async_add_executor_job(
            aurora_init
        )
        if AuroraPlus.Error:
            _LOGGER.debug("Error: %s", AuroraPlus.Error)
    except OSError as err:
        _LOGGER.error("Connection to Aurora+ failed: %s", err)

    async_add_entities([
        AuroraSensor(hass,
                     sensor, name,
                     AuroraPlus, rounding)
        for sensor in config.get(CONF_MONITORED_CONDITIONS)
    ],
        True)




class AuroraSensor(SensorEntity):
    """Representation of a Aurora+ sensor."""

    def __init__(self, hass, sensor, name, auroraplus, rounding):
        """Initialize the Aurora+ sensor."""
        self._hass = hass
        self._name = name + ' ' + sensor
        self._sensor = sensor
        self._unit_of_measurement = None
        self._state = None
        self._last_reset = None
        self._session = auroraplus
        self._uniqueid = self._name
        self._rounding = rounding
        _LOGGER.debug("Created sensor %s", self._sensor)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def last_reset(self):
        return self._last_reset

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return STATE_CLASS_TOTAL

    @property
    def device_class(self):
        """Return device class fo the sensor."""
        if self._sensor in SENSORS_MONETARY:
            return DEVICE_CLASS_MONETARY
        else:
            return DEVICE_CLASS_ENERGY

    @property
    def unique_id(self):
        """Return the unique_id of the sensor."""
        return self._uniqueid

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._sensor in SENSORS_MONETARY:
            return CURRENCY_DOLLAR
        else:
            return ENERGY_KILO_WATT_HOUR

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

    async def async_update(self):
        """Collect updated data from Aurora+ API."""
        def _api_update():
          try:
              _LOGGER.debug("Updating sensor: %s", self._sensor)
              self._session.getcurrent()
              self._session.getsummary()
              self._data = self._session
          except OSError as err:
              _LOGGER.error("Updating Aurora+ failed: %s", err)

        await self._hass.async_add_executor_job(_api_update)

        self._old_state = self._state
        if self._sensor == SENSOR_ESTIMATEDBALANCE:
            self._state = round(
                float(self._session.EstimatedBalance), self._rounding)
        elif self._sensor == SENSOR_DOLLARVALUEUSAGE:
            self._state = round(
                self._session.DollarValueUsage['Total'], self._rounding)
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:
            self._state = round(
                self._session.KilowattHourUsage['Total'], self._rounding)
        elif self._sensor.startswith(SENSOR_KILOWATTHOURUSAGETARIFF):
            tariff = self._sensor.removeprefix(SENSOR_KILOWATTHOURUSAGETARIFF)
            self._state = self._session.KilowattHourUsage.get(tariff)
            if self._state:
                self._state = round(self._state, self._rounding)
        else:
            _LOGGER.error("Unknown sensor type found")
        if self._old_state and self._state != self._old_state:
            self._last_reset = datetime.datetime.now()
