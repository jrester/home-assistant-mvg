"""Support for departure information for public transport in Munich."""

import logging

from mvg import MvgApi, TransportType, MvgApiError
import voluptuous as vol

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.components.sensor.const import SensorStateClass, SensorDeviceClass
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_LINES, CONF_STATION_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by mvg.de"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities = [
        MvgStationDeparturesSensor(entry.runtime_data, entry.data[CONF_STATION_NAME])
    ]
    for line in entry.options[CONF_LINES]:
        entities.append(
            MvgLineDeparturesSensor(
                entry.runtime_data, entry.data[CONF_STATION_NAME], line
            )
        )

    async_add_entities(entities)


class MvgEntity(CoordinatorEntity, SensorEntity):
    _attr_attribution = ATTRIBUTION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:clock"

    def __init__(self, coordinator: DataUpdateCoordinator, station_name: str) -> None:
        super().__init__(coordinator, station_name)
        self.station_name = station_name

    @property
    def native_value(self) -> int:
        if len(self.departures) == 0:
            return None
        return self.departures[0].minutes_until_real_departure()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        formatted_departures = []
        for departure in self.departures:
            formatted_departures.append(
                {
                    "planned": departure.minutes_until_planned_departure(),
                    "real": departure.minutes_until_real_departure(),
                    "destination": departure.destination,
                    "platform": departure.platform,
                    "realtime": departure.realtime,
                    "line": departure.line,
                    "cancelled": departure.cancelled,
                    "transport_type": departure.transport_type.value[0],
                }
            )
        return {"departures": formatted_departures}


class MvgStationDeparturesSensor(MvgEntity):
    def __init__(self, coordinator, station_name) -> None:
        super().__init__(coordinator, station_name)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name=self.name,
            identifiers={(DOMAIN, self.station_name)},
            manufacturer="MVG",
        )
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.entry_id}_{self.station_name}"
        )

    @property
    def departures(self) -> list:
        return self.coordinator.data

    @property
    def name(self) -> str:
        return f"{self.station_name}"


class MvgLineDeparturesSensor(MvgEntity):
    _attr_attribution = ATTRIBUTION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:clock"

    def __init__(
        self, coordinator: DataUpdateCoordinator, station_name: str, line_name: str
    ) -> None:
        super().__init__(coordinator, station_name)
        self.line_name = line_name
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name=self.name,
            identifiers={(DOMAIN, self.station_name, self.line_name)},
            manufacturer="MVG",
            via_device=(DOMAIN, self.station_name),
        )
        self._attr_unique_id = f"{self.coordinator.config_entry.entry_id}_{self.station_name}_{self.line_name}"

    @property
    def departures(self) -> list:
        return [
            departure
            for departure in self.coordinator.data
            if departure.line == self.line_name
        ]

    @property
    def name(self) -> str:
        return f"{self.station_name}: {self.line_name}"
