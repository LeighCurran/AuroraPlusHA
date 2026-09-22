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
from requests.exceptions import HTTPError

from auroraplus import AuroraPlusApi, AuroraPlusAuthenticationError

from .const import (
    CONF_SERVICE_AGREEMENT_ID,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    INTEGRATION_NAME,
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
        """Set up the coordinator.

        Load base info and current week to get available tariffs.
        """
        _LOGGER.debug("AuroraPlusDataCoordinator: _async_setup")
        try:
            await self.hass.async_add_executor_job(self.api.getweek)
        except AuroraPlusAuthenticationError as e:
            raise ConfigEntryAuthFailed("authentication failure on setup") from e
        except HTTPError as e:
            status_code = e.response.status_code
            if status_code in [401, 403]:
                raise ConfigEntryAuthFailed("authentication failure on setup") from e
            raise

        await self._update_config_entry_token()

        if not (hasattr(self.api, "week") and self.api.week.get("TariffTypes")):
            raise ConfigEntryNotReady("No tariffs in returned data, yet")

        self.tariff_types = self.api.week.get("TariffTypes")

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        _LOGGER.debug("AuroraPlusDataCoordinator: running _async_update_data...")
        try:
            await self._api_update()
        except PlatformNotReady:
            _LOGGER.exception("AuroraPlusDataCoordinator not ready for data update yet")

    async def _api_update(self):
        # _LOGGER.debug("AuroraPlusDataCoordinator: running _api_udate ...")
        try:
            await self.hass.async_add_executor_job(self.api.getcurrent)

            for i in range(-1, -10, -1):
                await self.hass.async_add_executor_job(self.api.getday, i)
                if not self.api.day["NoDataFlag"]:
                    await self.hass.async_add_executor_job(self.api.getsummary, i)
                    break
                _LOGGER.debug(f"No data at index {i}")

            await self.hass.async_add_executor_job(self.api.getpowerhour)
            _LOGGER.debug(
                f"AuroraPlusDataCoordinator: powerhour: {self.api.powerhour}"
            )

            _LOGGER.info(
                "AuroraPlusDataCoordinator: Successfully obtained data from "
                + self.api.day["StartDate"]
            )
        except AuroraPlusAuthenticationError as err:
            _LOGGER.exception(
                "AuroraPlusDataCoordinator: Authentication failure on update (AuroraPlus)"
            )
            raise ConfigEntryAuthFailed from err
        except HTTPError as err:
            status_code = err.response.status_code
            if status_code in [401, 403]:
                _LOGGER.exception(
                    "AuroraPlusDataCoordinator: Authentication failure on update (HTTP)"
                )
                raise ConfigEntryAuthFailed from err
            raise UpdateFailed(
                "AuroraPlusDataCoordinator: HTTP error on update"
            ) from err
        except Exception as err:
            raise UpdateFailed(
                "AuroraPlusDataCoordinator: Communication failure on update"
            ) from err

        await self._update_config_entry_token()

    async def _update_config_entry_token(self):
        _LOGGER.debug(
            "AuroraPlusDataCoordinator: running _update_config_entry_token ..."
        )
        if self.config_entry.state != ConfigEntryState.LOADED:
            _LOGGER.debug(
                f"AuroraPlusDataCoordinator: update_config_entry_token for {self.service_agreement_id} not ready yet; skipping token update "
            )
            return

        entry_token = self.config_entry.data.get(CONF_TOKEN)
        api_token = self.api.token
        if entry_token == api_token:
            _LOGGER.debug(
                f"AuroraPlusDataCoordinator: update_config_entry_token for {self.service_agreement_id} with unmodified token {entry_token=} == {api_token=}"
            )
            return

        # _LOGGER.debug(f"AuroraPlusDataCoordinator: update_config_entry_token setting to {api_token=}...")
        updated = self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                CONF_SERVICE_AGREEMENT_ID: self.service_agreement_id,
                CONF_TOKEN: api_token.copy(),
            },
        )
        _LOGGER.debug(
            f"AuroraPlusDataCoordinator: update_config_entry_token token updated: {updated=}"
        )

    @property
    def service_agreement_id(self) -> str:
        return self.api.serviceAgreementID
