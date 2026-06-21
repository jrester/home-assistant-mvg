"""Support for departure information for public transport in Munich."""

import logging
from datetime import datetime, tzinfo


from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor.const import SensorStateClass
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
                    "planned": _get_minutes_until_departure(departure.time),
                    "real": _get_minutes_until_departure(departure.planned),
                    "destination": departure.destination,
                    "platform": departure.platform,
                    "realtime": departure.realtime,
                    "line": departure.line,
                    "cancelled": departure.cancelled,
                    "transport_type": departure.transport_type,
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


def _get_minutes_until_departure(departure_time: int, tz: tzinfo | None = None) -> int:
    """Calculate the time difference in minutes between the current time and a given departure time.

    :param departure_time: unix timestamp of the departure time, in seconds
    :param tz: optional timezone information

    :return: the time difference in whole minutes

    """
    current_time = datetime.now(tz)
    departure_datetime = datetime.fromtimestamp(departure_time, tz)
    time_difference = (departure_datetime - current_time).total_seconds()
    return int(time_difference / 60.0)
