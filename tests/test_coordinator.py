import logging
from typing import Awaitable
from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_TOKEN
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.auroraplus.const import DOMAIN
from custom_components.auroraplus.coordinator import AuroraPlusCoordinator


async def test_async_setup(hass: HomeAssistant):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.mark.asyncio
@patch("custom_components.auroraplus.api.AuroraPlusApi")
async def test_setup(
    mock_auroraplus_api: MagicMock,
    mock_api: MagicMock,
    build_config_entry: Awaitable[ConfigEntry],
    caplog: pytest.LogCaptureFixture,
):
    # Return a Mock when trying to build the real thing.
    mock_auroraplus_api.return_value = mock_api

    config_entry = await build_config_entry(mock_api)
    assert "ERROR" not in caplog.text, "ERRORS in logging output"

    caplog.clear()

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


@pytest.mark.asyncio
async def test_update(
    mock_api: MagicMock,
    config_entry: ConfigEntry,
    caplog: pytest.LogCaptureFixture,
    hass: HomeAssistant,
):
    caplog.set_level("DEBUG")

    # Added by the fixture so we keep the same context.
    # hass = config_entry._hass

    coordinator: AuroraPlusCoordinator = config_entry.runtime_data

    def compare_tokens(
        config_entry: ConfigEntry,
        coordinator: AuroraPlusCoordinator,
        period: str,
        should_match: bool,
    ) -> tuple[dict, dict]:
        entry_token = config_entry.data.get(CONF_TOKEN)
        api_token = coordinator._api.token

        if not should_match:
            assert api_token != entry_token, f"Token data are the same {period}"

        else:
            assert api_token == entry_token, f"Token data differs {period}"
            assert api_token is not entry_token, (
                f"Token reference is shared between config and API {period}"
            )

        return entry_token.copy(), api_token.copy()

    # Tokens should be different prior to update, as the API got an updated one,
    # but the ConfigEntry was not ready to be updated yet.
    old_entry_token, old_api_token = compare_tokens(
        config_entry, coordinator, "prior to update", False
    )

    # Re-arm throttle, so the update applies.
    coordinator._throttle = {}

    with caplog.at_level(logging.DEBUG):
        await coordinator.async_update()
        # XXX: Does caplog work in async?
        # assert "token updated in config_entry:" in caplog.text

    assert mock_api.getcurrent.called
    assert mock_api.getday.called
    assert mock_api.getsummary.called

    new_entry_token, new_api_token = compare_tokens(
        config_entry, coordinator, "after update", True
    )

    assert new_api_token != old_api_token, "API token not updated"
    assert new_entry_token != old_entry_token, "ConfigEntry token not updated"
