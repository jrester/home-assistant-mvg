"""The mvg component."""

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import aiohttp_client

from mvg import MvgApi, MvgApiError

from .const import CONF_STATION_ID, CONF_TIME_OFFSET, UPDATE_INTERVAL, CONF_LIMIT
from .models import MvgDepartureInfo

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


class MvgDataManager(DataUpdateCoordinator):
    """Pull data from the mvg.de web page."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        station_id: str,
        timeoffset: int,
        limit: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"station {station_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.station_id = station_id
        self.timeoffset = timeoffset
        self.limit = limit
        self._session = aiohttp_client.async_get_clientsession(hass)

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Update the connection data."""
        try:
            departures = await MvgApi.departures_async(
                self.station_id,
                offset=self.timeoffset,
                limit=self.limit,
                session=self._session,
            )
            return [
                MvgDepartureInfo.from_dict(raw_departure)
                for raw_departure in departures
            ]
        except MvgApiError as exp:
            raise UpdateFailed(f"MVG API encountered an error: {exp}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    station_id = entry.data[CONF_STATION_ID]
    timeoffset = entry.data[CONF_TIME_OFFSET]
    limit = entry.data[CONF_LIMIT]

    coordinator = MvgDataManager(hass, entry, station_id, timeoffset, limit)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
