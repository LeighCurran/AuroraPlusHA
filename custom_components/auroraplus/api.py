import logging
from typing import Any

from auroraplus import AuroraPlusApi, AuroraPlusAuthenticationError
from requests.exceptions import HTTPError

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
)


_LOGGER = logging.getLogger(__name__)


def aurora_init(
    token: dict[str, Any] = {},
) -> AuroraPlusApi:
    _LOGGER.debug(f"aurora_init {token=}")
    try:
        # We need to copy the token, otherwise the AuroraPlusApi will use and update
        # the reference that it's been passed. If the reference comes from the
        # ConfigEntry, both will always hold the same value in memory. If they are
        # the same, HA will not persist the updated value.
        api = AuroraPlusApi(token=token.copy())

        # We need this data in AuroraPlusCoordinator.__init__so we have the
        # serviceAgreementID, preiseAddress, and tariffs over the previous
        # week however HomeAssistant is not happy if the calls are made there.

        api.get_info()
        api.getweek()

    except AuroraPlusAuthenticationError as e:
        raise ConfigEntryAuthFailed("authentication failure on init") from e
    except HTTPError as e:
        status_code = e.response.status_code
        if status_code in [401, 403]:
            raise ConfigEntryAuthFailed("authentication failure on init") from e
        raise e

    return api
