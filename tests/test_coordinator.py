from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.auroraplus.const import DOMAIN
from custom_components.auroraplus.coordinator import AuroraPlusCoordinator


async def test_async_setup(hass: HomeAssistant):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.mark.asyncio
async def test_setup(mock_api: MagicMock, config_entry: ConfigEntry):
    assert config_entry.state != ConfigEntryState.MIGRATION_ERROR, (
        "Encountered migration error despite using the AuroraPlusConfigFlow default"
    )

    assert config_entry.runtime_data, "ConfigEntry's runtime_data not set"
    assert isinstance(config_entry.runtime_data, AuroraPlusCoordinator), (
        "ConfigEntry's runtime_data not an AuroraPlusCoordinator"
    )
    coordinator: AuroraPlusCoordinator = config_entry.runtime_data

    assert coordinator.day

    assert mock_api.get_info.called
    assert mock_api.getcurrent.called
