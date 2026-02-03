"""Config flow for Brunata integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from brunata_api import Client

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.core import callback

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_DEBUG_LOGGING

_LOGGER = logging.getLogger(__name__)

async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = await hass.async_add_executor_job(Client, data[CONF_EMAIL], data[CONF_PASSWORD])
    
    try:
        # Forsøg at hente målere for at validere login
        _LOGGER.debug("Forsøger at validere login ved at hente målere for %s", data[CONF_EMAIL])
        # Biblioteket har en fejl med await på dict i _renew_tokens/_b2c_auth
        try:
            meters = await client.get_meters()
        except TypeError as err:
            if "await" in str(err) and "dict" in str(err):
                 _LOGGER.error("Fejl i brunata-api biblioteket: 'object dict can't be used in await expression'")
            raise InvalidAuth from err
        
        if meters:
            _LOGGER.debug("Login valideret, fandt %s målere", len(meters))
        else:
            _LOGGER.warning("Login valideret, men ingen målere fundet")
    except InvalidAuth:
        raise
    except Exception as err:
        _LOGGER.error("Kunne ikke validere Brunata login: %s", err)
        raise InvalidAuth from err

    return {"title": data[CONF_EMAIL]}

class BrunataConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brunata."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Uventet fejl")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BrunataOptionsFlowHandler:
        """Get the options flow for this handler."""
        return BrunataOptionsFlowHandler(config_entry)

class BrunataOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Brunata options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Brunata options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the Brunata options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DEBUG_LOGGING,
                        default=self.config_entry.options.get(CONF_DEBUG_LOGGING, False),
                    ): bool,
                }
            ),
        )

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
