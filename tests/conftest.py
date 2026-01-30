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
    mock_api.token = {}

    return mock_api


@pytest.fixture
@patch("custom_components.auroraplus.api.AuroraPlusApi")
async def config_entry(
    api: MagicMock, mock_api: MagicMock, hass: HomeAssistant
) -> ConfigEntry:
    api.return_value = mock_api

    config_entry = MockConfigEntry(
        version=AuroraPlusConfigFlow.VERSION,
        minor_version=AuroraPlusConfigFlow.MINOR_VERSION,
        domain=DOMAIN,
        data={
            CONF_SERVICE_AGREEMENT_ID: mock_api.serviceAgreementID,
            CONF_TOKEN: mock_api.token,
        },
    )

    assert await config_entry.setup_lock.acquire(), "Can't acquire setup lock; retry"
    await config_entry.async_setup(hass)
    config_entry.setup_lock.release()

    return config_entry


