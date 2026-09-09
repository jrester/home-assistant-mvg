import logging
from collections import defaultdict
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from mvg import MvgApi, TransportType

from .const import (
    CONF_LIMIT,
    CONF_LINES,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_TIME_OFFSET,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MvgConfgFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 1

    _title: str
    _station_metadata: dict[str, Any]
    _timeoffset: int
    _limit: int

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
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
            elif not errors:
                self._title = f"{station_metadata['name']} ({station_metadata['id']})"
                self._station_metadata = station_metadata
                self._timeoffset = timeoffset
                self._limit = user_input[CONF_LIMIT]
                return await self.async_step_select_lines()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION_NAME): str,
                    vol.Optional(CONF_TIME_OFFSET, default=5): int,
                    vol.Optional(CONF_LIMIT, default=10): int,
                }
            ),
            errors=errors,
        )

    async def async_step_select_lines(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(
                title=self._title,
                data={
                    CONF_STATION_ID: self._station_metadata["id"],
                    CONF_STATION_NAME: self._station_metadata["name"],
                    CONF_TIME_OFFSET: self._timeoffset,
                    CONF_LIMIT: self._limit,
                },
                options=user_input,
            )

        station_id = self._station_metadata["id"]
        selectable_lines = await _get_select_options_lines(station_id)

        print(selectable_lines)

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
    def async_get_options_flow(cls, config_entry: ConfigEntry) -> MvgOptionsFlowHandler:
        return MvgOptionsFlowHandler()


class MvgOptionsFlowHandler(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            _LOGGER.warning("Optiosn for MVG: %s", user_input)
            return self.async_create_entry(data=user_input)

        station_id = self.config_entry.data[CONF_STATION_ID]
        selectable_lines = await _get_select_options_lines(station_id)

        return self.async_show_form(
            step_id="select_lines",
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


async def _get_select_options_lines(station_id: str) -> list[SelectOptionDict]:
    lines = await MvgApi.lines_async(station_id)
    # The MVG lines result might contain multiple entries per line (e.g., S-BAHN and Bus SEV).
    # Since we later on, only filter by line name (S3, S1, etc.) we can safely merge them.
    # use `set` for the line labels, since MVG API returns all entries two times...
    deduplicated_lines = defaultdict(set)
    for line_info in lines:
        line_name = line_info["label"]

        # Avoid confusion when a train line is also marked as Bus due to SEV being potentially available.
        sev_label = " SEV" if line_info["sev"] else ""
        transport_type_label = TransportType[line_info["transportType"]].value[0]
        line_label = f"{transport_type_label}{sev_label}"

        deduplicated_lines[line_name].add(line_label)

    select_options = []
    for line_name, line_label_parts in deduplicated_lines.items():
        option_label = f"{line_name} ({', '.join(line_label_parts)})"
        select_option = SelectOptionDict(
            value=line_name,
            label=option_label,
        )
        select_options.append(select_option)

    return select_options
