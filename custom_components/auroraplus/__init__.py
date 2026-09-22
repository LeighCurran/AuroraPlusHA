"""The auroraplus sensor integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    PlatformNotReady,
)

from .api import aurora_init
from .const import CONF_TOKEN
from .coordinator import AuroraPlusDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up entry."""
    _LOGGER.debug("async_setup_entry")
    token = entry.data.get(CONF_TOKEN)

    try:
        api = await hass.async_add_executor_job(aurora_init, token)
    except OSError as err:
        raise PlatformNotReady("Connection to Aurora+ failed") from err

    coordinator = AuroraPlusDataCoordinator(hass, entry, api)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True
