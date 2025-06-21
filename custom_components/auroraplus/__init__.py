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

from .api import AuroraApi, aurora_init
from .const import DOMAIN
# from .sensor import async_setup_platform
from .sensor import async_setup_entry

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry):
    """Set up entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = dict(entry.data)

    access_token = entry.data.get(CONF_ACCESS_TOKEN)

    try:
        api_session = await hass.async_add_executor_job(
            aurora_init,
            access_token
        )
    except OSError as err:
        raise PlatformNotReady('Connection to Aurora+ failed') from err

    entry.async_on_unload(
        entry.add_update_listener(AuroraApi.update_listener)
    )

    entry.runtime_data = AuroraApi(hass, api_session)

    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor"]
    )

    return True
