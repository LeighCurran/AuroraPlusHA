from typing import Awaitable
from unittest.mock import MagicMock, patch

from auroraplus import AuroraPlusApi
from homeassistant.config_entries import ConfigEntry
import pytest
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.auroraplus.config_flow import AuroraPlusConfigFlow
from custom_components.auroraplus.const import CONF_SERVICE_AGREEMENT_ID, DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


@pytest.fixture
async def mock_api() -> AuroraPlusApi:
    mock_api = MagicMock()
    mock_api.serviceAgreementID = "mock_api_id"
    mock_api.premiseAddress = "mock_address"
    mock_api.token = {
        "access_token": "mock_access_token_init",
        "cookie_RefreshToken": "cookie_RefreshToken_init",
    }

    def update_token():
        if not hasattr(update_token, "call_count"):
            update_token.call_count = 0
        update_token.call_count += 1
        mock_api.token = {
            "access_token": f"mock_access_token_update_{update_token.call_count}",
            "cookie_RefreshToken": f"cookie_RefreshToken_update_{update_token.call_count}",
        }

    mock_api.getcurrent = MagicMock()
    mock_api.getcurrent.side_effect = update_token

    def update_day(index: int = -1):
        if not hasattr(update_day, "call_count"):
            update_day.call_count = 0
        update_day.call_count += 1
        update_token()
        mock_api.day = {
            "NoDataFlag": False,
            "StartDate": "2025-12-14T13:00:00Z",
            "update_day.call_count": update_day.call_count,
        }

    def update_week(index: int = -1):
        if not hasattr(update_week, "call_count"):
            update_week.call_count = 0
        update_week.call_count += 1
        update_token()
        mock_api.week = {
            "TariffTypes": ["T140", "T93OFFPEAK", "T93PEAK"],
            "update_week.call_count": update_week.call_count,
        }

    mock_api.getday = MagicMock()
    mock_api.getday.side_effect = update_day
    mock_api.getweek.side_effect = update_week

    return mock_api


@pytest.fixture
@patch("custom_components.auroraplus.api.AuroraPlusApi")
async def config_entry(
    auroraplus_api: MagicMock,
    mock_api: MagicMock,
    build_config_entry: Awaitable[ConfigEntry],
) -> ConfigEntry:
    # Return a Mock when trying to build the real thing.
    auroraplus_api.return_value = mock_api
    return await build_config_entry(mock_api)


@pytest.fixture
async def build_config_entry(hass: HomeAssistant) -> Awaitable[ConfigEntry]:

    async def _build_config_entry(api: AuroraPlusApi) -> ConfigEntry:
        config_entry = MockConfigEntry(
            version=AuroraPlusConfigFlow.VERSION,
            minor_version=AuroraPlusConfigFlow.MINOR_VERSION,
            domain=DOMAIN,
            data={
                CONF_SERVICE_AGREEMENT_ID: api.serviceAgreementID,
                # XXX: Using copy() here defeats the purpose of the first test for
                # identity in test_coordinator.test_update.
                CONF_TOKEN: api.token.copy(),
            },
            unique_id="config_entry_fixture",
        )
        config_entry.add_to_hass(hass)

        assert await config_entry.setup_lock.acquire(), (
            "Can't acquire setup lock; retry"
        )
        await config_entry.async_setup(hass)
        config_entry.setup_lock.release()

        return config_entry

    return _build_config_entry
