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
    _LOGGER.debug("Setting up Brunata sensors for entry %s", entry.entry_id)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    for meter_id, meter in coordinator.data.items():
        _LOGGER.debug("Creating BrunataSensor for meter %s", meter_id)
        entities.append(BrunataSensor(coordinator, meter))
    
    _LOGGER.debug("Adding %s entities", len(entities))
    async_add_entities(entities)

class BrunataSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Brunata meter."""

    def __init__(self, coordinator, meter):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._meter_id = meter._meter_id
        self._attr_unique_id = f"brunata_{self._meter_id}_consumption"
        self._attr_has_entity_name = True
        self._attr_translation_key = "consumption"
        self._attr_suggested_object_id = f"brunata_{self._meter_id}_consumption"

        # Handle unit and map m3 to m³
        raw_unit = meter.meter_unit or ""
        unit = raw_unit.lower()
        if unit == "m3":
            self._attr_native_unit_of_measurement = "m³"
        elif not unit:
            # For meters without unit (e.g. radiator meters) we use 'pts' (points)
            self._attr_native_unit_of_measurement = "pts"
        else:
            self._attr_native_unit_of_measurement = raw_unit

        # Determine device class and icon
        meter_type = meter.meter_type.lower()
        if unit in ["m³", "m3", "l"]:
            if "gas" in meter_type:
                self._attr_device_class = SensorDeviceClass.GAS
            else:
                self._attr_device_class = SensorDeviceClass.WATER
            self._attr_icon = "mdi:water"
        elif unit in ["kwh", "mwh"]:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_icon = "mdi:lightning-bolt"
        else:
            self._attr_icon = "mdi:gauge"
            
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_suggested_display_precision = 2

        # Group under a device per meter like in the MQTT script
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"brunata_{self._meter_id}")},
            name=f"Brunata {meter.meter_type} ({self._meter_id})",
            manufacturer="Brunata",
            model=meter.meter_type,
        )
        _LOGGER.debug("Initialized BrunataSensor for meter %s (%s)", self._meter_id, meter.meter_type)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        meter = self.coordinator.data.get(self._meter_id)
        if meter and meter.latest_reading:
            return meter.latest_reading.value
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        meter = self.coordinator.data.get(self._meter_id)
        if meter and meter.latest_reading:
            return {
                "reading_date": meter.latest_reading.date,
            }
        return {}
