import logging
from collections.abc import Awaitable
from unittest.mock import MagicMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.auroraplus.const import DOMAIN
from custom_components.auroraplus.coordinator import AuroraPlusDataCoordinator


async def test_async_setup(hass: HomeAssistant):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.mark.asyncio
@patch("custom_components.auroraplus.api.AuroraPlusApi")
# Prevent scheduling a task which makes the test fail when it's found to linger at the
# end.
@patch("homeassistant.helpers.debounce.Debouncer._schedule_timer")
@patch("homeassistant_historical_sensor.sensor.async_track_time_interval")
@patch(
    "custom_components.auroraplus.coordinator.DataUpdateCoordinator._schedule_refresh"
)
async def test_setup(
    _mock_schedule_refresh: Mock,
    _mock_async_track_time_interval: Mock,
    _mock_schedule_timer: Mock,
    mock_auroraplus_api: Mock,
    mock_api: Mock,
    build_config_entry: Awaitable[ConfigEntry],
    caplog: pytest.LogCaptureFixture,
):
    mock_api.CurrentTimeOfUseType = "PEAK"
    mock_api.CurrentTimeOfUsePeriodEndDate = "2025-12-26T11:00:01Z"

    # Return a Mock when trying to build the real thing.
    mock_auroraplus_api.return_value = mock_api

    config_entry = await build_config_entry(mock_api)
    assert "ERROR" not in caplog.text, "ERRORS in logging output"

    caplog.clear()

    assert config_entry.state != ConfigEntryState.MIGRATION_ERROR, (
        "Encountered migration error despite using the AuroraPlusConfigFlow default"
    )

    assert config_entry.runtime_data, "ConfigEntry's runtime_data not set"
    assert isinstance(config_entry.runtime_data, AuroraPlusDataCoordinator), (
        "ConfigEntry's runtime_data not an AuroraPlusDataCoordinator"
    )
    coordinator: AuroraPlusDataCoordinator = config_entry.runtime_data

    assert coordinator.api

    assert mock_api.get_info.called
    assert mock_api.getcurrent.called
    assert mock_api.getday.called


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

    coordinator: AuroraPlusDataCoordinator = config_entry.runtime_data

    def compare_tokens(
        config_entry: ConfigEntry,
        coordinator: AuroraPlusDataCoordinator,
        period: str,
        should_match: bool,
    ) -> tuple[dict, dict]:
        entry_token = config_entry.data.get(CONF_TOKEN)
        api_token = coordinator.api.token

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
        await coordinator._async_update_data()
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
