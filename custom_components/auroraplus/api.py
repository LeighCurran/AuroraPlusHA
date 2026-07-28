import logging
from typing import Any

import requests as plain_requests
from auroraplus import AuroraPlusApi, AuroraPlusAuthenticationError
from requests.exceptions import HTTPError

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
)


_LOGGER = logging.getLogger(__name__)


def oauth_refresh_token(token: dict[str, Any]) -> dict[str, Any] | None:
    """Use the OAuth B2C refresh_token to obtain a fresh id_token and refresh_token.

    Aurora's API no longer returns a RefreshToken cookie from the LoginToken
    endpoint, so the library's built-in refresh mechanism fails. This function
    uses the OAuth refresh_token (from the original auth) to get a new id_token,
    which can then be exchanged for a new access_token via LoginToken.
    """
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        _LOGGER.warning("No OAuth refresh_token available for token refresh")
        return None

    try:
        r = plain_requests.post(
            AuroraPlusApi.TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": AuroraPlusApi.CLIENT_ID,
                "scope": "openid offline_access",
            },
            timeout=30,
        )
        r.raise_for_status()
        new_token = r.json()
        _LOGGER.debug("OAuth refresh_token exchange succeeded")
        return new_token
    except Exception as e:
        _LOGGER.warning(f"OAuth refresh_token exchange failed: {e}")
        return None


def aurora_reinit(api: AuroraPlusApi, token: dict[str, Any]) -> bool:
    """Re-initialise an existing API object with a refreshed OAuth token.

    Returns True on success, False on failure.
    """
    new_token = oauth_refresh_token(token)
    if not new_token:
        return False

    # Merge the new OAuth fields into the existing token, preserving any extra keys
    token.update({
        "id_token": new_token["id_token"],
        "refresh_token": new_token.get("refresh_token", token.get("refresh_token")),
    })
    # Clear the stale access_token so the library re-obtains it via id_token
    token.pop("access_token", None)
    token.pop("cookie_RefreshToken", None)

    try:
        new_api = AuroraPlusApi(token=token.copy())
        new_api.get_info()

        # Ensure the OAuth refresh_token is preserved in the api token dict
        # so it survives into the config entry and can be used on future refreshes
        new_refresh = token.get("refresh_token")
        if new_refresh:
            new_api.token["refresh_token"] = new_refresh

        # Copy the refreshed state back onto the existing api object
        api.session = new_api.session
        api.token = new_api.token
        api.customerId = new_api.customerId
        api.serviceAgreementID = new_api.serviceAgreementID
        api.premiseAddress = new_api.premiseAddress
        api.Active = new_api.Active
        api.Error = new_api.Error
        _LOGGER.info("Successfully re-authenticated via OAuth refresh_token")
        return True
    except Exception as e:
        _LOGGER.warning(f"Re-init after OAuth refresh failed: {e}")
        return False


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

        # Preserve the OAuth refresh_token so it can be used for re-auth
        if "refresh_token" in token and "refresh_token" not in api.token:
            api.token["refresh_token"] = token["refresh_token"]

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
