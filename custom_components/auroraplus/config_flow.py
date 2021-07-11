from homeassistant import config_entries
from .const import DOMAIN


class AuroraPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """AuroraPlus config flow."""


