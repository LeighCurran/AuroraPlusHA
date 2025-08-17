"""The auroraplus sensor integration."""
import logging

from homeassistant.components.sensor.const import (
    SensorDeviceClass,
)
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ACCESS_TOKEN,
    CONF_NAME,
    CONF_MONITORED_CONDITIONS,
    CURRENCY_DOLLAR,
    CONF_SCAN_INTERVAL,
    UnitOfEnergy,
)
from homeassistant.exceptions import (
        ConfigEntryNotReady,
        PlatformNotReady,
)


from .api import aurora_init
from .const import CONF_TOKEN, CONF_ID_TOKEN, DOMAIN
from .coordinator import AuroraPlusCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry):
    """Set up entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = dict(entry.data)

    id_token = entry.data.get(CONF_ID_TOKEN)
    token = entry.data.get(CONF_TOKEN)

    try:
        api = await hass.async_add_executor_job(
            aurora_init,
            token,
            id_token
        )
    except OSError as err:
        raise PlatformNotReady('Connection to Aurora+ failed') from err

    entry.async_on_unload(
        entry.add_update_listener(AuroraPlusCoordinator.update_listener)
    )

    entry.runtime_data = AuroraPlusCoordinator(hass, entry, api)

    if not (
            hasattr(entry.runtime_data, "year")
            and entry.runtime_data.year.get("TariffTypes")
            ):
        raise ConfigEntryNotReady("No tariffs in returned data, yet")

    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor"]
    )

    return True
