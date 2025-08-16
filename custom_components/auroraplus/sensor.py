"""Support for Aurora+"""

import datetime
import logging

import voluptuous as vol

from homeassistant.exceptions import (
    ConfigEntryNotReady,
    IntegrationError,
)

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import StatisticsRow
from homeassistant.components.sensor.const import (
    SensorDeviceClass,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CURRENCY_DOLLAR,
    UnitOfEnergy,
)
from homeassistant_historical_sensor import (
    HistoricalSensor,
    HistoricalState,
    PollUpdateMixin,
)

from .api import aurora_init
from .const import (
    CONF_ROUNDING,
    DEFAULT_MONITORED,
    DEFAULT_ROUNDING,
    DOMAIN,
    SENSORS_MONETARY,
    SENSOR_DOLLARVALUEUSAGE,
    SENSOR_DOLLARVALUEUSAGETARIFF,
    SENSOR_ESTIMATEDBALANCE,
    SENSOR_KILOWATTHOURUSAGE,
    SENSOR_KILOWATTHOURUSAGETARIFF,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, config_entry, async_add_entities, discovery_info=None
):
    """Set up the Aurora+ platform for sensors."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    name = "AuroraPlus"
    rounding = config.get(CONF_ROUNDING, DEFAULT_ROUNDING)

    coordinator = config_entry.runtime_data
    await coordinator.async_update()

    tariffs = coordinator.month["TariffTypes"]
    if not tariffs:
        raise ConfigEntryNotReady("Empty tariffs in returned data")

    sensors_energy = [f"{SENSOR_KILOWATTHOURUSAGETARIFF} {t}" for t in tariffs]
    sensors_cost = [f"{SENSOR_DOLLARVALUEUSAGETARIFF} {t}" for t in tariffs]

    async_add_entities(
        [
            AuroraSensor(hass, sensor, name, coordinator, rounding)
            for sensor in config.get(CONF_MONITORED_CONDITIONS, DEFAULT_MONITORED)
        ]
        + [
            AuroraHistoricalSensor(hass, sensor, name, coordinator, rounding)
            for sensor in sensors_energy + sensors_cost
        ],
        True,
    )
    _LOGGER.info(f"Aurora+ platform ready with tariffs {tariffs}")


class AuroraSensor(SensorEntity):
    """Representation of a Aurora+ sensor."""

    def __init__(self, hass, sensor, name, coordinator, rounding):
        """Initialize the Aurora+ sensor."""
        self._hass = hass
        self._name = name + " " + coordinator.service_agreement_id + " " + sensor
        self._sensor = sensor
        self._unit_of_measurement = None
        self._state = None
        self._last_reset = None
        self._coordinator = coordinator
        self._uniqueid = self._name.replace(" ", "_").lower()
        self._rounding = rounding
        _LOGGER.debug(f"{self._sensor} created")

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
        return SensorStateClass.TOTAL

    @property
    def device_class(self):
        """Return device class fo the sensor."""
        if self._sensor in SENSORS_MONETARY:
            return SensorDeviceClass.MONETARY
        else:
            return SensorDeviceClass.ENERGY

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
            return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        if self._sensor == SENSOR_DOLLARVALUEUSAGE:
            return self._coordinator.DollarValueUsage
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:
            return self._coordinator.KilowattHourUsage
        elif self._sensor == SENSOR_ESTIMATEDBALANCE:
            attributes = {}
            attributes["Amount Owed"] = self._coordinator.AmountOwed
            attributes["Average Daily Usage"] = self._coordinator.AverageDailyUsage
            attributes["Usage Days Remaining"] = self._coordinator.UsageDaysRemaining
            attributes["Actual Balance"] = self._coordinator.ActualBalance
            attributes["Unbilled Amount"] = self._coordinator.UnbilledAmount
            attributes["Bill Total Amount"] = self._coordinator.BillTotalAmount
            attributes["Number Of Unpaid Bills"] = self._coordinator.NumberOfUnpaidBills
            attributes["Bill Overdue Amount"] = self._coordinator.BillOverDueAmount
            return attributes

    async def async_update(self):
        """Collect updated data from Aurora+ API."""
        await self._coordinator.async_update()

        self._old_state = self._state
        if self._sensor == SENSOR_ESTIMATEDBALANCE:
            estimated_balance = self._coordinator.EstimatedBalance
            try:
                self._state = round(float(estimated_balance), self._rounding)
            except TypeError:
                self._state = None
        elif self._sensor == SENSOR_DOLLARVALUEUSAGE:
            self._state = round(
                self._coordinator.DollarValueUsage.get("Total", float("nan")),
                self._rounding,
            )
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:
            self._state = round(
                self._coordinator.KilowattHourUsage.get("Total", float("nan")),
                self._rounding,
            )

        else:
            _LOGGER.warning(f"{self._sensor}: Unknown sensor type")
        if self._old_state and self._state != self._old_state:
            self._last_reset = datetime.datetime.now()


class AuroraHistoricalSensor(PollUpdateMixin, HistoricalSensor, SensorEntity):
    def __init__(self, hass, sensor, name, coordinator, rounding):
        """Initialize the Aurora+ sensor."""
        self._hass = hass
        self._name = name + " " + coordinator.service_agreement_id + " " + sensor
        self._sensor = sensor
        self._unit_of_measurement = None
        self._attr_historical_states = []
        self._coordinator = coordinator
        self._uniqueid = self._name.replace(" ", "_").lower()
        self._rounding = rounding
        _LOGGER.debug(f"{self._sensor} created (historical)")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    # @property
    # def state_class(self):
    #     """Return the state class of the sensor."""
    #     return SensorStateClass.TOTAL

    @property
    def device_class(self):
        """Return device class fo the sensor.
        This method does some string-parsing and error handling magic,
        so others don't have to, to determine the type of sensor.
        """
        if self._sensor.startswith(SENSOR_DOLLARVALUEUSAGETARIFF):
            return SensorDeviceClass.MONETARY
        elif self._sensor.startswith(SENSOR_KILOWATTHOURUSAGETARIFF):
            return SensorDeviceClass.ENERGY
        else:
            raise IntegrationError(f"{self._sensor} is not handled by {self.__class__}")

    @property
    def unique_id(self):
        """Return the unique_id of the sensor."""
        return self._uniqueid

    @property
    def statistic_id(self) -> str:
        return "sensor." + self._uniqueid

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.device_class == SensorDeviceClass.MONETARY:
            return CURRENCY_DOLLAR
        elif self.device_class == SensorDeviceClass.ENERGY:
            return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def historical_states(self):
        """Return the historical state of the sensor."""
        return self._attr_historical_states

    async def async_update_historical(self):
        if self.device_class == SensorDeviceClass.MONETARY:
            tariff = self._sensor.removeprefix(SENSOR_DOLLARVALUEUSAGETARIFF).strip()
            field = "DollarValueUsage"
        elif self._sensor.startswith(SENSOR_KILOWATTHOURUSAGETARIFF):
            tariff = self._sensor.removeprefix(SENSOR_KILOWATTHOURUSAGETARIFF).strip()
            field = "KilowattHourUsage"

        await self._coordinator.async_update()

        metered_records = self._coordinator.day.get("MeteredUsageRecords")
        if metered_records is None:
            _LOGGER.warning(
                f"{self._sensor}: no metered records, can't obtain hourly data"
            )
            return

        self._attr_historical_states = [
            HistoricalState(
                state=abs(float(r[field][tariff])),
                dt=datetime.datetime.fromisoformat(r["StartTime"]),
            )
            for r in metered_records
            if r and r.get(field) and r.get(field).get(tariff)
        ]

        if not self._attr_historical_states:
            _LOGGER.debug(
                f"{self._sensor}: empty historical states for tariff {tariff}"
            )

        _LOGGER.debug(
            f"{self._sensor}: historical states: %s", self._attr_historical_states
        )

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
        accumulated = latest.get("sum", 0) if latest else 0

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

        _LOGGER.debug(f"{self._sensor}: calculated statistics %s", ret)
        return ret
