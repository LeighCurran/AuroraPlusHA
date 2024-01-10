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

from homeassistant.exceptions import (
    IntegrationError,
    PlatformNotReady,
)

from homeassistant.components.recorder.models import (StatisticData,
                                                      StatisticMetaData)
from homeassistant.components.recorder.statistics import StatisticsRow

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

from homeassistant_historical_sensor import (
    HistoricalSensor,
    HistoricalState,
    PollUpdateMixin,
)

CONF_ROUNDING = "rounding"


_LOGGER = logging.getLogger(__name__)

SENSOR_ESTIMATEDBALANCE = 'Estimated Balance'
SENSOR_DOLLARVALUEUSAGE = 'Dollar Value Usage'
SENSOR_KILOWATTHOURUSAGE = 'Kilowatt Hour Usage'
SENSOR_KILOWATTHOURUSAGETARIFF = 'Kilowatt Hour Usage Tariff'
SENSOR_DOLLARVALUEUSAGETARIFF = 'Dollar Value Usage Tariff'

SENSORS_MONETARY = [
    SENSOR_ESTIMATEDBALANCE,
    SENSOR_DOLLARVALUEUSAGE,
]


POSSIBLE_MONITORED = SENSORS_MONETARY + [SENSOR_KILOWATTHOURUSAGE]

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
            session = auroraplus.api(username, password)
            session.getmonth()
            return session
        AuroraPlus = await hass.async_add_executor_job(
            aurora_init
        )
    except OSError as err:
        raise PlatformNotReady('Connection to Aurora+ failed') from err

    try:
        tariffs = AuroraPlus.month['TariffTypes']
        if not tariffs:
            raise KeyError('Empty tariffs in returned data')
    except KeyError as err:
        raise PlatformNotReady('Data not available yet') from err

    sensors_energy = [
        f'{SENSOR_KILOWATTHOURUSAGETARIFF} {t}'
        for t in tariffs
    ]
    sensors_cost = [
        f'{SENSOR_DOLLARVALUEUSAGETARIFF} {t}'
        for t in tariffs
    ]

    aurora_api = AuroraApi(hass, AuroraPlus)
    await aurora_api.async_update()

    async_add_entities([
        AuroraSensor(hass,
                     sensor, name,
                     aurora_api, rounding)
        for sensor in config.get(CONF_MONITORED_CONDITIONS)
    ] + [
        AuroraHistoricalSensor(hass,
                               sensor, name,
                               aurora_api, rounding)
        for sensor in sensors_energy + sensors_cost
    ],
        True)
    _LOGGER.info(f'Aurora+ platform ready with tariffs {tariffs}')


class AuroraApi():
    """Asynchronously-updating wrapper for the Aurora API. """
    _hass = None
    _session = None

    def __init__(self, hass, session):
        self._hass = hass
        self._session = session
        _LOGGER.debug(f'AuroraApi ready with {self._session}')

    @Throttle(min_time=DEFAULT_SCAN_INTERVAL)  # XXX: should be configurable
    async def async_update(self):
        await self._hass.async_add_executor_job(self._api_update)

    def _api_update(self):
        try:
            self._session.gettoken()
            self._session.getcurrent()
            for i in range(-1, - 10, - 1):
                self._session.getday(i)
                if not self._session.day['NoDataFlag']:
                    self._session.getsummary(i)
                    break
                _LOGGER.debug(f'No data at index {i}')
            _LOGGER.info('Successfully obtained data from '
                         + self._session.day['StartDate'])
        except Exception as e:
            _LOGGER.warn(f'Error updating data: {e}')

    def __getattr__(self, attr):
        """Forward any attribute access to the session, or handle error """
        if attr == '_throttle':
            raise AttributeError()
        _LOGGER.debug(f'Accessing data for {attr}')
        try:
            data = getattr(self._session, attr)
        except AttributeError as err:
            _LOGGER.debug(
                f'Data for {attr} not yet available'
            )
            return {}  # empty with a get
        _LOGGER.debug(f'... returning {data}')
        return data


class AuroraSensor(SensorEntity):
    """Representation of a Aurora+ sensor."""

    def __init__(self, hass, sensor, name, aurora_api, rounding):
        """Initialize the Aurora+ sensor."""
        self._hass = hass
        self._name = name + ' ' + sensor
        self._sensor = sensor
        self._unit_of_measurement = None
        self._state = None
        self._last_reset = None
        self._api = aurora_api
        self._uniqueid = self._name.replace(' ', '_').lower()
        self._rounding = rounding
        _LOGGER.debug(f'{self._sensor} created')

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
            return self._api.DollarValueUsage
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:
            return self._api.KilowattHourUsage
        elif self._sensor == SENSOR_ESTIMATEDBALANCE:
            attributes = {}
            attributes['Amount Owed'] = self._api.AmountOwed
            attributes['Average Daily Usage'] = self._api.AverageDailyUsage
            attributes['Usage Days Remaining'] = self._api.UsageDaysRemaining
            attributes['Actual Balance'] = self._api.ActualBalance
            attributes['Unbilled Amount'] = self._api.UnbilledAmount
            attributes['Bill Total Amount'] = self._api.BillTotalAmount
            attributes['Number Of Unpaid Bills'] = self._api.NumberOfUnpaidBills
            attributes['Bill Overdue Amount'] = self._api.BillOverDueAmount
            return attributes

    async def async_update(self):
        """Collect updated data from Aurora+ API."""
        await self._api.async_update()

        self._old_state = self._state
        if self._sensor == SENSOR_ESTIMATEDBALANCE:
            self._state = round(
                float(self._api.EstimatedBalance), self._rounding)
        elif self._sensor == SENSOR_DOLLARVALUEUSAGE:
            self._state = round(
                self._api.DollarValueUsage.get('Total', float('nan')),
                self._rounding)
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:
            self._state = round(
                self._api.KilowattHourUsage.get('Total', float('nan')),
                self._rounding)

        else:
            _LOGGER.warn(f'{self._sensor}: Unknown sensor type')
        if self._old_state and self._state != self._old_state:
            self._last_reset = datetime.datetime.now()


class AuroraHistoricalSensor(PollUpdateMixin, HistoricalSensor, SensorEntity):
    def __init__(self, hass, sensor, name, aurora_api, rounding):
        """Initialize the Aurora+ sensor."""
        self._hass = hass
        self._name = name + ' ' + sensor
        self._sensor = sensor
        self._unit_of_measurement = None
        self._attr_historical_states = []
        self._api = aurora_api
        self._uniqueid = self._name.replace(' ', '_').lower()
        self._rounding = rounding
        _LOGGER.debug(f'{self._sensor} created (historical)')

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    # @property
    # def state_class(self):
    #     """Return the state class of the sensor."""
    #     return STATE_CLASS_TOTAL

    @property
    def device_class(self):
        """Return device class fo the sensor.
        This method does some string-parsing and error handling magic,
        so others don't have to, to determine the type of sensor.
        """
        if self._sensor.startswith(SENSOR_DOLLARVALUEUSAGETARIFF):
            return DEVICE_CLASS_MONETARY
        elif self._sensor.startswith(SENSOR_KILOWATTHOURUSAGETARIFF):
            return DEVICE_CLASS_ENERGY
        else:
            raise IntegrationError(
                f'{self._sensor} is not handled by {self.__class__}'
            )

    @property
    def unique_id(self):
        """Return the unique_id of the sensor."""
        return self._uniqueid

    @property
    def statistic_id(self) -> str:
        return 'sensor.' + self._uniqueid

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.device_class == DEVICE_CLASS_MONETARY:
            return CURRENCY_DOLLAR
        elif self.device_class == DEVICE_CLASS_ENERGY:
            return ENERGY_KILO_WATT_HOUR

    @property
    def historical_states(self):
        """Return the historical state of the sensor."""
        return self._attr_historical_states

    async def async_update_historical(self):
        if self.device_class == DEVICE_CLASS_MONETARY:
            tariff = self._sensor.removeprefix(
                SENSOR_DOLLARVALUEUSAGETARIFF
            ).strip()
            field = 'DollarValueUsage'
        elif self._sensor.startswith(SENSOR_KILOWATTHOURUSAGETARIFF):
            tariff = self._sensor.removeprefix(
                SENSOR_KILOWATTHOURUSAGETARIFF
            ).strip()
            field = 'KilowattHourUsage'

        await self._api.async_update()

        metered_records = self._api.day.get(
            'MeteredUsageRecords'
        )
        if metered_records is None:
            _LOGGER.warning(
                f"{self._sensor}: no metered records, can't obtain hourly data"
            )
            return

        self._attr_historical_states = [
            HistoricalState(
                state=abs(float(r[field][tariff])),
                dt=datetime.datetime.fromisoformat(r['StartTime'])
            )
            for r in metered_records
            if r
            and r.get(field)
            and r.get(field).get(tariff)
        ]

        if not self._attr_historical_states:
            _LOGGER.debug(
                f"{self._sensor}: empty historical states for tariff {tariff}"
            )

        _LOGGER.debug(f'{self._sensor}: historical states: %s',
                      self._attr_historical_states)

    def get_statistic_metadata(self) -> StatisticMetaData:
        meta = super().get_statistic_metadata()
        meta["has_sum"] = True

        return meta

    async def async_calculate_statistic_data(
        self,
        hist_states: list[HistoricalState],
        *,
        latest: StatisticsRow | None = None,
    ) -> list[StatisticData]:
        """Calculate statistics over multiple sampling periods.

        This code works for both energy and monetary sensors by fluke: The
        Aurora+ API returns hourly energy consumption only, and daily monetary
        cost only, both as part of the same data array. The format allows us to
        calculate correct statistics by simply ignoring the empty records.
        """
        accumulated = latest.get('sum', 0) if latest else 0

        ret = []

        for hs in hist_states:
            accumulated = accumulated + hs.state
            ret.append(
                StatisticData(
                    start=hs.dt,
                    state=hs.state,
                    sum=accumulated,
                )
            )

        _LOGGER.debug(f'{self._sensor}: calculated statistics %s',
                      ret)
        return ret
