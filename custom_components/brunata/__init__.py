"""The Brunata integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from brunata_api import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Brunata from a config entry."""
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    client = await hass.async_add_executor_job(Client, email, password)
    coordinator = BrunataDataUpdateCoordinator(hass, client)

    # Hent data første gang
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

class BrunataDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Brunata data."""

    def __init__(self, hass: HomeAssistant, client: Client):
        """Initialize."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            # Vi henter målere uden startdate for at få de absolut nyeste målinger
            # for alle målere. Brunatas API returnerer den første måling i en periode
            # hvis man angiver startdate, hvilket giver forældede data.
            await self.client._get_tokens()
            await self.client._init_mappers()

            from brunata_api.const import API_URL, METERS_URL
            from brunata_api import Meter

            # Hent alle målere med deres seneste status
            result = (
                await self.client.api_wrapper(
                    method="GET",
                    url=f"{API_URL}/consumer/meters",
                    headers={
                        "Referer": METERS_URL,
                    },
                )
            ).json()

            for item in result:
                json_meter = item.get("meter")
                if not json_meter:
                    continue
                
                # Filtrer målere uden superAllocationUnit (ofte ikke-aktive eller interne enheder)
                if json_meter.get("superAllocationUnit") is None:
                    continue
                
                json_reading = item.get("reading")
                meter_id = str(json_meter.get("meterId"))
                
                _LOGGER.debug("Behandler måler %s: %s", meter_id, json_meter.get("meterNo"))
                
                meter = self.client._meters.get(meter_id)
                if meter is None:
                    meter = Meter(self.client, json_meter)
                    self.client._meters[meter_id] = meter
                
                if json_reading and json_reading.get("value") is not None:
                    _LOGGER.debug("Tilføjer aflæsning for %s: %s (dato: %s)", meter_id, json_reading.get("value"), json_reading.get("readingDate"))
                    meter.add_reading(json_reading)

            if not self.client._meters:
                _LOGGER.warning("Ingen målere fundet. Forsøger standard hentning via get_meters().")
                meters = await self.client.get_meters()
                return {meter._meter_id: meter for meter in meters}

            # Returner en kopi af ordbogen for at sikre at koordinatoren opdager ændringer
            return dict(self.client._meters)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
