import logging
from typing import Any, override

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    PlatformNotReady,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import Throttle
from requests.exceptions import HTTPError

from auroraplus import AuroraPlusApi, AuroraPlusAuthenticationError

from .const import (
    CONF_SERVICE_AGREEMENT_ID,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    INTEGRATION_NAME,
    SENSOR_DOLLARVALUEUSAGE,
    SENSOR_DOLLARVALUEUSAGETARIFF,
    SENSOR_ESTIMATEDBALANCE,
    SENSOR_KILOWATTHOURUSAGE,
    SENSOR_KILOWATTHOURUSAGETARIFF,
)

_LOGGER = logging.getLogger(__name__)


class AuroraPlusDataCoordinator(DataUpdateCoordinator):
    api: AuroraPlusApi
    tariff_types: list[str]

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: AuroraPlusApi
    ):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=f"{INTEGRATION_NAME} Coordinator",
            config_entry=config_entry,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=DEFAULT_SCAN_INTERVAL,
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=True,
        )
        self.api = api

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator

        This is the place to set up your coordinator,
        or to load data, that only needs to be loaded once.

        This method will be called automatically during
        coordinator.async_config_entry_first_refresh.
        """
        try:
            await self.hass.async_add_executor_job(self.api.get_info)
            await self.hass.async_add_executor_job(self.api.getweek)
        except AuroraPlusAuthenticationError as e:
            raise ConfigEntryAuthFailed("authentication failure on setup") from e
        except HTTPError as e:
            status_code = e.response.status_code
            if status_code in [401, 403]:
                raise ConfigEntryAuthFailed("authentication failure on setup") from e
            raise e

        await self._update_config_entry_token()

        if not (hasattr(self.api, "week") and self.api.get("TariffTypes")):
            raise ConfigEntryNotReady("No tariffs in returned data, yet")

        self.tariff_types = self.api.week.get("TariffTypes")

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            await self.hass.async_add_executor_job(self.api.getcurrent)

            for i in range(-1, -10, -1):
                await self.hass.async_add_executor_job(self.api.getday, i)
                if not self.api.day["NoDataFlag"]:
                    await self.hass.async_add_executor_job(self.api.getsummary, i)
                    break
                _LOGGER.debug(f"No data at index {i}")
            _LOGGER.info("Successfully obtained data from " + self.api.day["StartDate"])
        except AuroraPlusAuthenticationError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except HTTPError as err:
            status_code = err.response.status_code
            if status_code in [401, 403]:
                raise ConfigEntryAuthFailed("authentication failure on update") from err
            raise UpdateFailed("communication failure on update") from err
        except Exception as err:
            raise UpdateFailed("communication failure on update") from err

        await self._update_config_entry_token()

        self.data = {
            SENSOR_ESTIMATEDBALANCE: {},
            SENSOR_DOLLARVALUEUSAGE: {},
            SENSOR_KILOWATTHOURUSAGE: {},
        }
        self.data.update(
            {
                f"{sensor} {tariff}": {}
                for sensor in [
                    SENSOR_KILOWATTHOURUSAGETARIFF,
                    SENSOR_DOLLARVALUEUSAGETARIFF,
                ]
                for tariff in self.tariff_types
            }
        )

    async def _update_config_entry_token(self):
        if self.config_entry.state != ConfigEntryState.LOADED:
            _LOGGER.debug(
                f"update_config_entry_token for {self.service_agreement_id} not ready yet; skipping token update "
            )
            return

        entry_token = self.config_entry.data.get(CONF_TOKEN)
        api_token = self.api.token
        if entry_token == api_token:
            _LOGGER.debug(
                f"update_config_entry_token for {self.service_agreement_id} with unmodified token {entry_token=} == {api_token=}"
            )
            return

        _LOGGER.debug(f"update_config_entry_token setting to {api_token=}...")
        updated = self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                CONF_SERVICE_AGREEMENT_ID: self.service_agreement_id,
                CONF_TOKEN: api_token.copy(),
            },
        )
        _LOGGER.debug(f"update_config_entry_token token updated: {updated=}")

    @property
    def service_agreement_id(self) -> str:
        return self.api.serviceAgreementID


class AuroraPlusCoordinator:
    """Asynchronously-updating wrapper for the AuroraPlus API."""

    hass: HomeAssistant
    config_entry: ConfigEntry

    _api: AuroraPlusApi

    service_agreement_id: str
    service_address: str

    _instances = {}

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: AuroraPlusApi
    ):
        self.hass = hass
        self.config_entry = config_entry
        self._api = api
        self.service_agreement_id = api.serviceAgreementID
        self.service_address = api.premiseAddress
        self.__class__._instances[self.service_agreement_id] = self
        _LOGGER.debug(f"AuroraPlusCoordinator ready with {self._api}")

    @Throttle(min_time=DEFAULT_SCAN_INTERVAL)  # XXX: should be configurable
    async def async_update(self):
        _LOGGER.debug("running async_update ...")
        try:
            _LOGGER.debug(f"... {self._throttle=}")
        except:  # noqa: E722
            _LOGGER.debug("... no throttle")
        try:
            await self._api_update()
        except PlatformNotReady as exc:
            _LOGGER.warning("AuroraPlusCoordinator not ready for data update yet")
            _LOGGER.exception(exc)

    async def _api_update(self):
        try:
            await self.hass.async_add_executor_job(self._api.getcurrent)

            for i in range(-1, -10, -1):
                await self.hass.async_add_executor_job(self._api.getday, i)
                if not self._api.day["NoDataFlag"]:
                    await self.hass.async_add_executor_job(self._api.getsummary, i)
                    break
                _LOGGER.debug(f"No data at index {i}")
            _LOGGER.info(
                "Successfully obtained data from " + self._api.day["StartDate"]
            )
        except AuroraPlusAuthenticationError as e:
            _LOGGER.exception(f"authentication failure on update: {e}")
            self.config_entry.async_start_reauth(self.hass)
        except HTTPError as e:
            status_code = e.response.status_code
            if status_code in [401, 403]:
                _LOGGER.exception(f"authentication failure on update: {e}")
                self.config_entry.async_start_reauth(self.hass)
            raise e
        except Exception as e:
            _LOGGER.exception(f"authentication failure on update: {e}")

        await self.update_config_entry_token(self.hass, self.config_entry)

    @classmethod
    async def update_config_entry_token(
        cls, hass: HomeAssistant, config_entry: ConfigEntry
    ):
        service_agreement_id = config_entry.data.get(CONF_SERVICE_AGREEMENT_ID)
        if config_entry.state != ConfigEntryState.LOADED:
            _LOGGER.debug(
                f"update_config_entry_token for {service_agreement_id} not ready yet; skipping token update "
            )
            return

        entry_token = config_entry.data.get(CONF_TOKEN)
        api_token = cls._instances[service_agreement_id]._api.token
        if entry_token == api_token:
            _LOGGER.debug(
                f"update_config_entry_token for {service_agreement_id} with unmodified token {entry_token=} == {api_token=}"
            )
            return

        _LOGGER.debug(f"update_config_entry_token setting to {api_token=}...")
        updated = hass.config_entries.async_update_entry(
            config_entry,
            data={
                CONF_SERVICE_AGREEMENT_ID: service_agreement_id,
                CONF_TOKEN: api_token.copy(),
            },
        )
        _LOGGER.debug(f"update_config_entry_token token updated: {updated=}")

    def __getattr__(self, attr: str) -> Any:
        """Forward any attribute access to the session, or handle error"""
        if attr == "_throttle":
            raise AttributeError()
        # _LOGGER.debug(f"Accessing data for {attr}")
        try:
            data = getattr(self._api, attr)
        except AttributeError:
            _LOGGER.debug(f"Data for {attr} not yet available")
            return {}  # empty with a get
        # _LOGGER.debug(f"... returning {data}")
        return data
