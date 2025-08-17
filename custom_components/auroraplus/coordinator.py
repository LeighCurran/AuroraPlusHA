import logging

from auroraplus import AuroraPlusApi, AuroraPlusAuthenticationError
from requests.exceptions import HTTPError

from homeassistant.const import (
    CONF_ACCESS_TOKEN,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, PlatformNotReady
from homeassistant.util import Throttle

from .api import aurora_init
from .const import (
    CONF_TOKEN,
    CONF_ID_TOKEN,
    CONF_SERVICE_AGREEMENT_ID,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class AuroraPlusCoordinator:
    """Asynchronously-updating wrapper for the AuroraPlus API."""

    _hass = None
    _api: AuroraPlusApi = None
    _config_entry = None

    _instances = {}

    def __init__(self, hass, config_entry, api):
        self._hass = hass
        self._config_entry = config_entry
        self._api = api
        self.service_agreement_id = api.serviceAgreementID
        self.service_address = api.month["ServiceAgreements"][api.serviceAgreementID][
            "PremiseName"
        ]
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
            await self._hass.async_add_executor_job(self._api_update)
        except PlatformNotReady as exc:
            _LOGGER.warning("AuroraPlusCoordinator not ready for data update yet")
            _LOGGER.exception(exc)

        self._hass.config_entries.async_update_entry(
            self._config_entry,
            data={
                CONF_ACCESS_TOKEN: self._api.token.get("access_token"),
                CONF_ID_TOKEN: self._api.token.get("id_token"),
                CONF_SERVICE_AGREEMENT_ID: self._api.serviceAgreementID,
                CONF_TOKEN: self._api.token,
            },
        )

    def _api_update(self):
        try:
            self._api.get_info()

            self._api.getcurrent()
            for i in range(-1, -10, -1):
                self._api.getday(i)
                if not self._api.day["NoDataFlag"]:
                    self._api.getsummary(i)
                    break
                _LOGGER.debug(f"No data at index {i}")
            _LOGGER.info(
                "Successfully obtained data from " + self._api.day["StartDate"]
            )
        except AuroraPlusAuthenticationError as e:
            raise ConfigEntryAuthFailed("authentication failure on update") from e
        except HTTPError as e:
            status_code = e.response.status_code
            if status_code in [401, 403]:
                raise ConfigEntryAuthFailed("authentication failure on update") from e
            raise e

    @classmethod
    async def update_listener(cls, hass, config_entry):
        """
        XXX: find the api object for the entitie, and update its session token
        """
        service_agreement_id = config_entry.data.get(CONF_SERVICE_AGREEMENT_ID)
        token = config_entry.data.get(CONF_TOKEN)
        if token == cls._instances[service_agreement_id]._api.token:
            _LOGGER.debug(
                f"update_listener for {service_agreement_id} with unmodified token"
            )
            return

        if token:
            _LOGGER.debug(f"update_listener for {service_agreement_id} with {token=}")
            api = await hass.async_add_executor_job(aurora_init, token)
        elif id_token := config_entry.data.get(CONF_ID_TOKEN):
            _LOGGER.debug(
                f"update_listener for {service_agreement_id} with {id_token=}"
            )
            api = await hass.async_add_executor_job(aurora_init, {}, id_token)
        elif access_token := config_entry.data.get(CONF_ACCESS_TOKEN):
            _LOGGER.debug(
                f"update_listener for {service_agreement_id} with {access_token=}"
            )
            api = await hass.async_add_executor_job(aurora_init, {}, None, access_token)
        else:
            _LOGGER.warning(
                "update_listener for {service_agreement_id} with no usable token"
            )
            return

        cls._instances[service_agreement_id].update_api(api)

    def update_api(self, api):
        _LOGGER.debug(f"updating {self=} to use {api=}")
        self._api = api

    def __getattr__(self, attr):
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
