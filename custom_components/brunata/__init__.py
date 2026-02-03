"""The Brunata integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from brunata_api import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_DEBUG_LOGGING

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Brunata from a config entry."""
    if entry.options.get(CONF_DEBUG_LOGGING):
        _LOGGER.setLevel(logging.DEBUG)
        _LOGGER.debug("Debug logging aktiveret via indstillinger")

    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    client = await hass.async_add_executor_job(Client, email, password)
    coordinator = BrunataDataUpdateCoordinator(hass, client)

    # Hent data første gang
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)

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
            
            # Biblioteket har en fejl hvor det forsøger at awaite en dict
            # i _get_tokens -> _renew_tokens og _b2c_auth.
            # Vi pakker det ind i en try-except for at give en bedre fejlbesked
            # hvis det fejler i biblioteket.
            try:
                await self.client._get_tokens()
                await self.client._init_mappers()
            except TypeError as err:
                if "await" in str(err) and "dict" in str(err):
                    _LOGGER.error("Fejl i brunata-api biblioteket: 'object dict can't be used in await expression'. Sørg for at have en rettet version af biblioteket eller kontakt udvikleren.")
                raise UpdateFailed(f"Fejl ved kommunikation med Brunata API via biblioteket: {err}") from err

            from brunata_api.const import API_URL, METERS_URL
            from brunata_api import Meter

            # Hent alle målere med deres seneste status
            response = await self.client.api_wrapper(
                method="GET",
                url=f"{API_URL}/consumer/meters",
                headers={
                    "Referer": METERS_URL,
                },
            )
            
            if response is None:
                _LOGGER.warning("Ingen respons fra API'et (timeout eller forbindelsesfejl)")
                return self.client._meters

            _LOGGER.debug("API-svar fra /consumer/meters: %s", response.text)
            
            try:
                result = response.json()
            except Exception as json_err:
                _LOGGER.error("Fejl ved parsing af JSON fra API: %s. Svar: %s", json_err, response.text)
                return self.client._meters

            if not isinstance(result, list):
                _LOGGER.error("Uventet API-svar format: forventede liste, fik %s. Svar: %s", type(result), response.text)
                return self.client._meters

            for item in result:
                if not isinstance(item, dict):
                    continue
                    
                json_meter = item.get("meter")
                if not isinstance(json_meter, dict):
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
                
                if isinstance(json_reading, dict) and json_reading.get("value") is not None:
                    _LOGGER.debug(
                        "Tilføjer aflæsning for %s: %s (dato: %s). Rå data: %s",
                        meter_id,
                        json_reading.get("value"),
                        json_reading.get("readingDate"),
                        json_reading,
                    )
                    meter.add_reading(json_reading)

            if not self.client._meters:
                _LOGGER.warning("Ingen målere fundet. Forsøger standard hentning via get_meters().")
                try:
                    meters = await self.client.get_meters()
                    if meters:
                        return {meter._meter_id: meter for meter in meters}
                except Exception as get_meters_err:
                    _LOGGER.error("Fejl ved kald til get_meters(): %s", get_meters_err)

            # Returner en kopi af ordbogen for at sikre at koordinatoren opdager ændringer
            return dict(self.client._meters)
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Uventet fejl ved hentning af data: {err}") from err
