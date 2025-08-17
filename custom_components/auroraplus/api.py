import logging

from auroraplus import AuroraPlusApi, AuroraPlusAuthenticationError
from requests.exceptions import HTTPError

from homeassistant.const import (
    CONF_ACCESS_TOKEN,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, PlatformNotReady
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
    _LOGGER.debug(f"aurora_init {token=} {id_token=} {access_token=}")
    try:
        api = AuroraPlusApi(token=token, id_token=id_token, access_token=access_token)

        # We need this data pulled so we can get the serviceAgreementID in
        # AuroraPlusCoordinator.__init__, however HomeAssistant is not happy if the calls are made
        # there.
        api.get_info()
        api.getmonth()

    except AuroraPlusAuthenticationError as e:
        raise ConfigEntryAuthFailed("authentication failure on init") from e
    except HTTPError as e:
        status_code = e.response.status_code
        if status_code in [401, 403]:
            raise ConfigEntryAuthFailed("authentication failure on init") from e
        raise e

    return api
