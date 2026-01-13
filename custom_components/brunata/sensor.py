"""Support for Brunata meters."""
from __future__ import annotations

import logging
from datetime import timedelta
from brunata_api import Client

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Brunata sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    for meter_id, meter in coordinator.data.items():
        entities.append(BrunataSensor(coordinator, meter))
    
    async_add_entities(entities)

class BrunataSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Brunata meter."""

    def __init__(self, coordinator, meter):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._meter_id = meter._meter_id
        self._attr_unique_id = f"brunata_{self._meter_id}_consumption"
        self._attr_name = f"Brunata {self._meter_id} Consumption"
        self._attr_native_unit_of_measurement = meter.meter_unit

        # Bestem device class og ikon
        unit = meter.meter_unit.lower()
        if unit in ["m³", "m3", "l"]:
            self._attr_device_class = SensorDeviceClass.WATER
            self._attr_icon = "mdi:water"
        elif unit in ["kwh", "mwh"]:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_icon = "mdi:lightning-bolt"
        else:
            self._attr_icon = "mdi:gauge"
            
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        # Gruppér under en enhed pr. måler ligesom i MQTT scriptet
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"brunata_{self._meter_id}")},
            name=f"Brunata {meter.meter_type} ({self._meter_id})",
            manufacturer="Brunata",
            model=meter.meter_type,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        meter = self.coordinator.data.get(self._meter_id)
        if meter:
            return meter.latest_reading.value
        return None
