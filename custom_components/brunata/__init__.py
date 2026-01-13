"""The Brunata integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

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

    client = Client(email, password)

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            meters = await client.get_meters()
            return {meter._meter_id: meter for meter in meters}
        except Exception as err:
            raise UpdateFailed(f"Fejl ved kontakt til Brunata API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Brunata",
        update_method=async_update_data,
        update_interval=timedelta(hours=24), # Brunata opdaterer typisk kun en gang i døgnet
    )

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
            update_interval=timedelta(hours=24),
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            # Hvis vi ikke har data endnu, henter vi historik
            if not self.data:
                # Vi har erfaret at for lange intervaller kan returnere 0 elementer
                # Vi prøver med 90 dage i stedet for 365 for at være mere sikre på bid
                _LOGGER.info("Henter historiske Brunata målinger (90 dage tilbage)")
                start_date = datetime.now() - timedelta(days=90)
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

                # Vi skal kalde update_meters manuelt med vores start_date
                # da get_meters() altid bruger dags dato i brunata-api 0.1.6
                await self.client._get_tokens()
                await self.client._init_mappers()

                # Vi bruger api_wrapper direkte for at styre startdate
                from brunata_api.const import API_URL, METERS_URL
                from brunata_api import Meter

                result = (
                    await self.client.api_wrapper(
                        method="GET",
                        url=f"{API_URL}/consumer/meters",
                        params={
                            "startdate": f"{start_date.isoformat()}.000Z",
                        },
                        headers={
                            "Referer": METERS_URL,
                        },
                    )
                ).json()

                for item in result:
                    json_meter = item.get("meter")
                    if not json_meter or json_meter.get("superAllocationUnit") is None:
                        continue
                    
                    json_reading = item.get("reading")
                    meter_id = str(json_meter.get("meterId"))
                    
                    meter = self.client._meters.get(meter_id)
                    if meter is None:
                        from brunata_api import Meter
                        meter = Meter(self.client, json_meter)
                        self.client._meters[meter_id] = meter
                    
                    if json_reading:
                        meter.add_reading(json_reading)

                if not self.client._meters:
                    _LOGGER.warning("Ingen målere fundet i historik-opslaget. Forsøger standard hentning.")
                    return await self.client.get_meters()

                return self.client._meters

            # Ellers bare almindelig opdatering
            meters = await self.client.get_meters()
            return {meter._meter_id: meter for meter in meters}
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
