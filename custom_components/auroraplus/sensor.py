"""Support for Aurora+"""

import datetime
import logging
from typing import Any


from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    IntegrationError,
)

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
    CURRENCY_DOLLAR,
    UnitOfEnergy,
)

from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from homeassistant_historical_sensor import (
    HistoricalSensor,
    HistoricalState,
    PollUpdateMixin,
)

from custom_components.auroraplus.coordinator import AuroraPlusCoordinator

from .const import (
    DEFAULT_MONITORED,
    DEFAULT_ROUNDING,
    SENSORS_MONETARY,
    SENSOR_DOLLARVALUEUSAGE,
    SENSOR_DOLLARVALUEUSAGETARIFF,
    SENSOR_ESTIMATEDBALANCE,
    SENSOR_KILOWATTHOURUSAGE,
    SENSOR_KILOWATTHOURUSAGETARIFF,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
):
    """Set up the Aurora+ platform for sensors."""
    name = "AuroraPlus"
    rounding = DEFAULT_ROUNDING

    coordinator = config_entry.runtime_data
    await coordinator.async_update()

    tariffs = coordinator.week.get("TariffTypes")

    sensors_energy = [f"{SENSOR_KILOWATTHOURUSAGETARIFF} {t}" for t in tariffs]
    sensors_cost = [f"{SENSOR_DOLLARVALUEUSAGETARIFF} {t}" for t in tariffs]

    async_add_entities(
        [
            AuroraSensor(hass, sensor, name, coordinator, rounding)
            for sensor in DEFAULT_MONITORED
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

    _hass: HomeAssistant
    name: str
    _sensor: str
    _raw_state: Any  # XXX
    last_reset: datetime.datetime
    _coordinator: AuroraPlusCoordinator
    unique_id: str
    _rounding: int

    def __init__(
        self,
        hass: HomeAssistant,
        sensor: str,
        name: str,
        coordinator: AuroraPlusCoordinator,
        rounding: int,
    ):
        """Initialize the Aurora+ sensor."""
        self._hass = hass
        self.name = name + " " + coordinator.service_agreement_id + " " + sensor
        self._sensor = sensor
        self._raw_state = None
        self.last_reset = datetime.datetime.strptime("1970", "%Y")
        self._coordinator = coordinator
        self.unique_id = self.name.replace(" ", "_").lower()
        self._rounding = rounding
        _LOGGER.debug(f"{self._sensor} created")

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class of the sensor."""
        return SensorStateClass.TOTAL

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return device class fo the sensor."""
        if self._sensor in SENSORS_MONETARY:
            return SensorDeviceClass.MONETARY
        else:
            return SensorDeviceClass.ENERGY

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        if self._sensor in SENSORS_MONETARY:
            return CURRENCY_DOLLAR
        else:
            return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def extra_state_attributes(self) -> Any:
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

        previous_state = self._raw_state
        if self._sensor == SENSOR_ESTIMATEDBALANCE:
            estimated_balance = self._coordinator.EstimatedBalance
            try:
                self._raw_state = round(float(estimated_balance), self._rounding)
            except TypeError:
                self._raw_state = None
        elif self._sensor == SENSOR_DOLLARVALUEUSAGE:
            self._raw_state = round(
                self._coordinator.DollarValueUsage.get("Total", float("nan")),
                self._rounding,
            )
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:
            self._raw_state = round(
                self._coordinator.KilowattHourUsage.get("Total", float("nan")),
                self._rounding,
            )

        else:
            _LOGGER.warning(f"{self._sensor}: Unknown sensor type")
        if previous_state and self._raw_state != previous_state:
            self.last_reset = datetime.datetime.now()


class AuroraHistoricalSensor(PollUpdateMixin, HistoricalSensor, SensorEntity):
    _hass: HomeAssistant
    name: str
    _sensor: str
    _attr_historical_states: list[HistoricalState]
    _coordinator: AuroraPlusCoordinator
    unique_id: str
    _rounding: int

    def __init__(
        self,
        hass: HomeAssistant,
        sensor: str,
        name: str,
        coordinator: AuroraPlusCoordinator,
        rounding: int,
    ):
        """Initialize the Aurora+ sensor."""
        self._hass = hass
        self.name = name + " " + coordinator.service_agreement_id + " " + sensor
        self._sensor = sensor
        self._attr_historical_states = []
        self._coordinator = coordinator
        self.unique_id = self.name.replace(" ", "_").lower()
        self._rounding = rounding
        _LOGGER.debug(f"{self._sensor} created (historical)")

    @property
    def device_class(self) -> SensorDeviceClass:
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
    def statistic_id(self) -> str:
        return "sensor." + self.unique_id

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if self.device_class == SensorDeviceClass.MONETARY:
            return CURRENCY_DOLLAR
        elif self.device_class == SensorDeviceClass.ENERGY:
            return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def historical_states(self) -> list[HistoricalState]:
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
