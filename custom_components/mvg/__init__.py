"""The mvg component."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import aiohttp_client

from mvg import MvgApi, TransportType, MvgApiError

from .const import CONF_STATION_ID, CONF_TIME_OFFSET, UPDATE_INTERVAL, CONF_LIMIT

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


class MvgDataManager(DataUpdateCoordinator):
    """Pull data from the mvg.de web page."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        mvg_api: MvgApi,
        timeoffset: int,
        limit: int,
    ):
        """Initialize the sensor."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"station {mvg_api.station_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self._mvg_api = mvg_api
        self.station_id = mvg_api.station_id
        self.timeoffset = timeoffset
        self.limit = limit

    async def _async_update_data(self):
        """Update the connection data."""
        try:
            departures = await self._mvg_api.departures_async(
                offset=self.timeoffset, limit=self.limit
            )
            return departures
        except MvgApiError as exp:
            raise UpdateFailed(f"MVG API encountered an error: {exp}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    station_id = entry.data[CONF_STATION_ID]
    timeoffset = entry.data[CONF_TIME_OFFSET]
    limit = entry.data[CONF_LIMIT]

    client_session = aiohttp_client.async_get_clientsession(hass)
    mvg_api = await MvgApi.create_for_station_async(station_id, client_session)

    coordinator = MvgDataManager(hass, entry, mvg_api, timeoffset, limit)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
