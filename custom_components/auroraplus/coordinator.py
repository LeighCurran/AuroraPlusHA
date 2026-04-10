import logging
from typing import Any

from homeassistant.core import HomeAssistant

from auroraplus import AuroraPlusApi, AuroraPlusAuthenticationError
from requests.exceptions import HTTPError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import Throttle

from .const import (
    CONF_TOKEN,
    CONF_SERVICE_AGREEMENT_ID,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class AuroraPlusCoordinator:
    """Asynchronously-updating wrapper for the AuroraPlus API."""

    _hass: HomeAssistant
    _api: AuroraPlusApi
    _config_entry: ConfigEntry

    service_agreement_id: str
    service_address: str

    _instances = {}

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: AuroraPlusApi
    ):
        self._hass = hass
        self._config_entry = config_entry
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
            await self._hass.async_add_executor_job(self._api.getcurrent)

            for i in range(-1, -10, -1):
                await self._hass.async_add_executor_job(self._api.getday, i)
                if not self._api.day["NoDataFlag"]:
                    await self._hass.async_add_executor_job(self._api.getsummary, i)
                    break
                _LOGGER.debug(f"No data at index {i}")
            _LOGGER.info(
                "Successfully obtained data from " + self._api.day["StartDate"]
            )
        except AuroraPlusAuthenticationError as e:
            _LOGGER.exception(f"authentication failure on update: {e}")
            self._config_entry.async_start_reauth(self._hass)
        except HTTPError as e:
            status_code = e.response.status_code
            if status_code in [401, 403]:
                _LOGGER.exception(f"authentication failure on update: {e}")
                self._config_entry.async_start_reauth(self._hass)
            raise e
        except Exception as e:
            _LOGGER.exception(f"authentication failure on update: {e}")

        await self.update_config_entry_token(self._hass, self._config_entry)

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
