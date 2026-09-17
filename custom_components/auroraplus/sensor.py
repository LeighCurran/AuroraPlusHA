"""Support for Aurora+"""

import datetime
import logging

# from abc import abstractmethod
from typing import Any

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import StatisticsRow
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.sensor.const import (
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CURRENCY_DOLLAR,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    IntegrationError,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant_historical_sensor import (
    HistoricalSensor,
    HistoricalState,
)

from custom_components.auroraplus.coordinator import AuroraPlusCoordinator

from .const import (
    DEFAULT_MONITORED,
    DEFAULT_ROUNDING,
    INTEGRATION_NAME,
    SENSOR_DOLLARVALUEUSAGE,
    SENSOR_DOLLARVALUEUSAGETARIFF,
    SENSOR_ESTIMATEDBALANCE,
    SENSOR_KILOWATTHOURUSAGE,
    SENSOR_KILOWATTHOURUSAGETARIFF,
    SENSORS_MONETARY,
    UNIT_CLASS_ENERGY,
    UNIT_CLASS_MONETARY,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
):
    """Set up the Aurora+ platform for sensors."""
    rounding = DEFAULT_ROUNDING

    coordinator: AuroraPlusCoordinator = config_entry.runtime_data
    await coordinator.async_update()

    tariffs = coordinator.week.get("TariffTypes")

    sensors_energy = [f"{SENSOR_KILOWATTHOURUSAGETARIFF} {t}" for t in tariffs]
    sensors_cost = [f"{SENSOR_DOLLARVALUEUSAGETARIFF} {t}" for t in tariffs]

    async_add_entities(
        [AuroraSensor(sensor, coordinator, rounding) for sensor in DEFAULT_MONITORED]
        + [
            AuroraHistoricalSensor(sensor, coordinator, rounding)
            for sensor in sensors_energy + sensors_cost
        ],
        True,
    )

    _LOGGER.info(f"Aurora+ platform ready with tariffs {tariffs}")


class AuroraSensor(SensorEntity):
    """Representation of a Aurora+ sensor."""

    _attr_state_class: str | None = SensorStateClass.TOTAL
    _coordinator: AuroraPlusCoordinator
    _rounding: int = DEFAULT_ROUNDING
    _sensor: str

    _attr_device_class: str | None = None
    _attr_native_unit_of_measurement: str | None = None
    _attr_extra_state_attributes: dict[str | Any]  # update in update

    _sensor_mode = ""

    def __init__(
        self,
        sensor: str,
        coordinator: AuroraPlusCoordinator,
        rounding: int = DEFAULT_ROUNDING,
    ):
        """Initialize the Aurora+ sensor."""
        super().__init__()

        self._attr_name = (
            f"{INTEGRATION_NAME} {coordinator.service_agreement_id} {sensor}"
        )
        self._sensor = sensor
        self._attr_native_value = None
        if self.state_class == SensorStateClass.TOTAL:
            self._attr_last_reset = datetime.datetime.strptime(
                "1970", "%Y"
            ).astimezone()
        self._coordinator = coordinator
        self._attr_unique_id = self._attr_name.replace(" ", "_").lower()
        self._rounding = rounding
        _LOGGER.debug(f"{self._sensor} created{self._sensor_mode}")

        self._attr_device_class = self._get_device_class()
        self._attr_native_unit_of_measurement = self._get_unit_of_measurement()

    def _get_device_class(self) -> SensorDeviceClass | None:
        """Return device class fo the sensor."""
        if any(self._sensor.startswith(p) for p in SENSORS_MONETARY):
            return SensorDeviceClass.MONETARY
        else:
            return SensorDeviceClass.ENERGY

    def _get_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if self.device_class == SensorDeviceClass.MONETARY:
            return CURRENCY_DOLLAR
        elif self.device_class == SensorDeviceClass.ENERGY:
            return UnitOfEnergy.KILO_WATT_HOUR
        raise IntegrationError(
            f"Sensor {self._sensor} is not handled by {self.__class__} (unit of measurement)"
        )

    async def async_update(self):
        """Collect updated data from Aurora+ API."""
        await self._coordinator.async_update()

        previous_state = (
            self._attr_native_value
            if self.state_class == SensorStateClass.TOTAL
            else None
        )
        self._attr_native_value = self._fetch_state_from_coordinator()
        self._attr_extra_state_attributes = self._fetch_attributes_from_coordinator()

        if previous_state and self._attr_native_value != previous_state:
            self._attr_last_reset = datetime.datetime.now().astimezone()

    # @abstractmethod
    def _fetch_state_from_coordinator(self):
        if self._sensor == SENSOR_ESTIMATEDBALANCE:
            estimated_balance = self._coordinator.EstimatedBalance
            try:
                return round(float(estimated_balance), self._rounding)
            except TypeError:
                _LOGGER.warning(f"{self._sensor}: EstimatedBalance not present")
                return None
        elif self._sensor == SENSOR_DOLLARVALUEUSAGE:
            return round(
                self._coordinator.DollarValueUsage.get("Total", float("nan")),
                self._rounding,
            )
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:
            return round(
                self._coordinator.KilowattHourUsage.get("Total", float("nan")),
                self._rounding,
            )

        else:
            _LOGGER.warning(f"{self._sensor}: Unknown sensor type")

    # @abstractmethod
    def _fetch_attributes_from_coordinator(self) -> dict[str, Any]:
        """Return device state attributes."""
        if self._sensor == SENSOR_DOLLARVALUEUSAGE:
            return self._coordinator.DollarValueUsage
        elif self._sensor == SENSOR_KILOWATTHOURUSAGE:
            return self._coordinator.KilowattHourUsage
        elif self._sensor == SENSOR_ESTIMATEDBALANCE:
            attributes = {}
            attributes["amount_owed"] = self._coordinator.AmountOwed
            attributes["average_daily_usage"] = self._coordinator.AverageDailyUsage
            attributes["usage_days_remaining"] = self._coordinator.UsageDaysRemaining
            attributes["actual_balance"] = self._coordinator.ActualBalance
            attributes["unbilled_amount"] = self._coordinator.UnbilledAmount
            attributes["bill_total_amount"] = self._coordinator.BillTotalAmount
            attributes["number_of_unpaid_bills"] = self._coordinator.NumberOfUnpaidBills
            attributes["bill_overdue_amount"] = self._coordinator.BillOverDueAmount
            return attributes
        return {}


class AuroraHistoricalSensor(HistoricalSensor, AuroraSensor):
    _sensor_mode = " (historical)"

    _unit_class: str
    _attr_historical_states: list[HistoricalState]

    def __init__(
        self,
        sensor: str,
        coordinator: AuroraPlusCoordinator,
        rounding: int,
    ):
        """Initialize the Aurora+ sensor."""
        AuroraSensor.__init__(self, sensor, coordinator, rounding)

        self._unit_class = self._get_unit_class()
        self._attr_historical_states = []

    async def async_update(self):
        pass

    async def async_update_historical(self):
        field, tariff = self._get_state_field_and_tariff()

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
                timestamp=datetime.datetime.fromisoformat(r["StartTime"]).timestamp(),
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
        meta["unit_class"] = self.unit_class
        meta["unit_of_measurement"] = self.unit_of_measurement

        return meta

    def _get_unit_class(self) -> str:
        """Return the unit of measurement."""
        if self.device_class == SensorDeviceClass.MONETARY:
            return UNIT_CLASS_MONETARY
        elif self.device_class == SensorDeviceClass.ENERGY:
            return UNIT_CLASS_ENERGY
        raise IntegrationError(
            f"Device class {self.device_class} for {self._sensor} is not handled by {self.__class__} (unit class)"
        )

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
                    start=datetime.datetime.fromtimestamp(hs.timestamp, datetime.UTC),
                    state=hs.state,
                    sum=accumulated,
                )
            )

        _LOGGER.debug(f"{self._sensor}: calculated statistics %s", ret)
        return ret

    @property
    def unit_class(self) -> str:
        """Return the unit of measurement."""
        return self._unit_class

    # @abstractmethod
    def _get_state_field_and_tariff(self) -> (str, str):
        if self.device_class == SensorDeviceClass.MONETARY:
            tariff = self._sensor.removeprefix(SENSOR_DOLLARVALUEUSAGETARIFF).strip()
            field = "DollarValueUsage"
            return field, tariff
        if self._sensor.startswith(SENSOR_KILOWATTHOURUSAGETARIFF):
            tariff = self._sensor.removeprefix(SENSOR_KILOWATTHOURUSAGETARIFF).strip()
            field = "KilowattHourUsage"
            return field, tariff
        raise IntegrationError(f"Sensor {self._sensor} doesn't have field and tariffs")
