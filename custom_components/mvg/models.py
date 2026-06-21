from typing import Any, Self

from dataclasses import dataclass
from datetime import datetime


def _get_minutes_until_departure(departure_time: int) -> int:
    """Calculate the time difference in minutes between the current time and a given departure time.

    Args:
        departure_time: Unix timestamp of the departure time, in seconds.

    Returns:
        The time difference in minutes, as a float.

    """
    current_time = datetime.now()
    departure_datetime = datetime.fromtimestamp(departure_time)
    time_difference = (departure_datetime - current_time).total_seconds()
    minutes_difference = int(time_difference / 60.0)
    return minutes_difference


@dataclass
class MvgDepartureInfo:
    time: int
    planned: int
    delay: int | None
    line: str
    platform: int | None
    realtime: bool
    destination: str
    transport_type: str
    cancelled: bool
    messages: list[str]

    def minutes_until_planned_departure(self) -> int:
        return _get_minutes_until_departure(self.planned)

    def minutes_until_real_departure(self) -> int:
        return _get_minutes_until_departure(self.time)

    @classmethod
    def from_dict(cls, raw_departure_info: dict[str, Any]) -> Self:
        return cls(
            time=raw_departure_info["time"],
            planned=raw_departure_info["planned"],
            delay=raw_departure_info["delay"],
            platform=raw_departure_info["platform"],
            realtime=raw_departure_info["realtime"],
            line=raw_departure_info["line"],
            destination=raw_departure_info["destination"],
            transport_type=raw_departure_info["type"],
            cancelled=raw_departure_info["cancelled"],
            messages=raw_departure_info["messages"],
        )
