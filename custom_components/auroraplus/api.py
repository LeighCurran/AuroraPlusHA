import logging

import auroraplus
from requests.exceptions import HTTPError

from homeassistant.const import (
    CONF_ACCESS_TOKEN,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import Throttle

from .const import (
    CONF_TOKEN,
    CONF_ID_TOKEN,
    CONF_SERVICE_AGREEMENT_ID,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def aurora_init(
    token: dict = {},
    id_token: str | None = None,
    access_token: str | None = None,
):
    try:
        session = auroraplus.api(
            token=token, id_token=id_token, access_token=access_token
        )

        # We need this data pulled so we can get the serviceAgreementID in
        # AuroraApi.__init__, however HomeAssistant is not happy if the calls are made
        # there.
        session.get_info()
        session.getmonth()

    except HTTPError as e:
        status_code = e.response.status_code
        if status_code in [401, 403]:
            raise ConfigEntryAuthFailed(e) from e
        raise e

    return session


class AuroraApi:
    """Asynchronously-updating wrapper for the Aurora API."""

    _hass = None
    _session = None
    _config_entry = None

    _instances = {}

    def __init__(self, hass, config_entry, session):
        self._hass = hass
        self._config_entry = config_entry
        self._session = session
        self.service_agreement_id = session.serviceAgreementID
        self.service_address = session.month["ServiceAgreements"][
            session.serviceAgreementID
        ]["PremiseName"]
        self.__class__._instances[self.service_agreement_id] = self
        _LOGGER.debug(f"AuroraApi ready with {self._session}")

    @Throttle(min_time=DEFAULT_SCAN_INTERVAL)  # XXX: should be configurable
    async def async_update(self):
        try:
            await self._hass.async_add_executor_job(self._api_update)
        except PlatformNotReady as exc:
            _LOGGER.warning("AuroraPlusCoordinator not ready for data update yet")
            _LOGGER.exception(exc)

    def _api_update(self):
        try:
            self._session.get_info()
            token = self._session.token
            _LOGGER.debug(self)
            _LOGGER.debug(self._hass)
            # _LOGGER.debug(self.hass)
            _LOGGER.debug(self._hass.config)
            self._hass.config_entries.async_update_entry(
                self._config_entry,
                data={
                    CONF_ACCESS_TOKEN: self._api.token.get("access_token"),
                    CONF_ID_TOKEN: self._api.token.get("id_token"),
                    CONF_SERVICE_AGREEMENT_ID: self._api.serviceAgreementID,
                    CONF_TOKEN: self._api.token,
                },
            )
            self._session.getcurrent()
            for i in range(-1, -10, -1):
                self._session.getday(i)
                if not self._session.day["NoDataFlag"]:
                    self._session.getsummary(i)
                    break
                _LOGGER.debug(f"No data at index {i}")
            _LOGGER.info(
                "Successfully obtained data from " + self._session.day["StartDate"]
            )
        except HTTPError as e:
            status_code = e.response.status_code
            if status_code in [401, 403]:
                raise ConfigEntryAuthFailed(e) from e
            raise e
        except Exception as e:
            _LOGGER.warning(f"Error updating data: {e}")
            _LOGGER.exception(e)

    @classmethod
    async def update_listener(cls, hass, config_entry):
        """
        XXX: find the api object for the entitie, and update its session token
        """
        service_agreement_id = config_entry.data.get(CONF_SERVICE_AGREEMENT_ID)
        id_token = config_entry.data.get(CONF_ID_TOKEN)
        if not id_token:
            access_token = config_entry.data.get(CONF_ACCESS_TOKEN)
            session = await hass.async_add_executor_job(
                aurora_init, {}, None, access_token
            )
        else:
            session = await hass.async_add_executor_job(aurora_init, {}, id_token)
        api = cls._instances[service_agreement_id].update_session(session)

    def update_session(self, session):
        self._session = session

    def __getattr__(self, attr):
        """Forward any attribute access to the session, or handle error"""
        if attr == "_throttle":
            raise AttributeError()
        _LOGGER.debug(f"Accessing data for {attr}")
        try:
            data = getattr(self._session, attr)
        except AttributeError as err:
            _LOGGER.debug(f"Data for {attr} not yet available")
            return {}  # empty with a get
        _LOGGER.debug(f"... returning {data}")
        return data
