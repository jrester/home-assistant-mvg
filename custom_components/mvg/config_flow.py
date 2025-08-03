import logging
from typing import Any

from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigEntry,
    SubentryFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_DEVICE_ID, CONF_PORT
import voluptuous as vol

from mvg import MvgApi

from .const import (
    CONF_LINES,
    DOMAIN,
    CONF_STATION_NAME,
    CONF_STATION_ID,
    CONF_TIME_OFFSET,
)

_LOGGER = logging.getLogger(__name__)


class MvgConfgFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 1

    _title: str
    _station_metadata: dict[str, Any]
    _timeoffset: int

    async def async_step_user(self, user_input: dict[str, Any] | None):
        errors: dict[str, str] | None = {}
        if user_input is not None:
            timeoffset = user_input[CONF_TIME_OFFSET]
            if timeoffset < 0:
                errors[CONF_TIME_OFFSET] = "Timeoffset must not be negative!"

            station_name = user_input[CONF_STATION_NAME]
            station_metadata = await MvgApi.station_async(station_name)
            if station_metadata is None:
                errors[CONF_STATION_NAME] = (
                    f"Station {station_name} could not be found!"
                )

            if not errors:
                self._title = f"{station_metadata.name} ({station_metadata.station_id})"
                self._station_metadata = station_metadata
                self._timeoffset = timeoffset
                return await self.async_step_select_lines()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION_NAME): str,
                    vol.Optional(CONF_TIME_OFFSET, default=5): int,
                }
            ),
            errors=errors,
        )

    async def async_step_select_lines(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(
                title=self._title,
                data={
                    CONF_STATION_ID: self._station_metadata.station_id,
                    CONF_STATION_NAME: self._station_metadata.name,
                    CONF_TIME_OFFSET: 5,
                },
                options=user_input,
            )

        mvg_api = await MvgApi.create_for_station_async(
            self._station_metadata.station_id
        )
        lines = await mvg_api.lines_at_station_async()

        selectable_lines = [
            SelectOptionDict(
                value=line_info.name,
                label=f"{line_info.name} ({line_info.transport_type.value[0]})",
            )
            for line_info in lines
            if not line_info.sev
        ]

        return self.async_show_form(
            step_id="select_lines",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LINES): SelectSelector(
                        SelectSelectorConfig(
                            options=selectable_lines,
                            multiple=True,
                            sort=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    @classmethod
    @callback
    def async_get_options_flow(
        cls, config_entry: ConfigEntry
    ) -> "MvgOptionsFlowHandler":
        return MvgOptionsFlowHandler()


class MvgOptionsFlowHandler(OptionsFlowWithReload):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            _LOGGER.warning("Optiosn for MVG: %s", user_input)
            return self.async_create_entry(data=user_input)

        mvg_api = MvgApi(self.config_entry.data[CONF_STATION_ID])
        lines = await mvg_api.lines_at_station_async()

        selectable_lines = [
            SelectOptionDict(
                value=line_info.name,
                label=f"{line_info.name} ({line_info.transport_type.value[0]})",
            )
            for line_info in lines
            if not line_info.sev
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_LINES): SelectSelector(
                            SelectSelectorConfig(
                                options=selectable_lines,
                                multiple=True,
                                sort=True,
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    }
                ),
                self.config_entry.options,
            ),
        )
