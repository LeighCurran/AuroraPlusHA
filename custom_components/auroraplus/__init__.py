"""The auroraplus sensor integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    PlatformNotReady,
)


from .api import aurora_init
from .const import CONF_TOKEN
from .coordinator import AuroraPlusCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up entry."""
    token = entry.data.get(CONF_TOKEN)

    try:
        api = await hass.async_add_executor_job(aurora_init, token)
    except OSError as err:
        raise PlatformNotReady("Connection to Aurora+ failed") from err

    entry.runtime_data = AuroraPlusCoordinator(hass, entry, api)

    if not (
        hasattr(entry.runtime_data, "week")
        and entry.runtime_data.week.get("TariffTypes")
    ):
        raise ConfigEntryNotReady("No tariffs in returned data, yet")

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await AuroraPlusCoordinator.update_config_entry_token(hass, entry)
    return True
