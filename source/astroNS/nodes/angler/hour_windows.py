"""
Shared hour-of-day window lookup for what-if scenario scheduling.

A window is a dict with ``start_hour`` / ``end_hour`` (wall-clock hours,
0-23) plus type-specific payload fields (``availability``,
``latency_multiplier``, ``capacity_bps``, ...). Used by
DataCenterEndpoint (outage_windows), NetworkSegment (degrade_windows),
and SiteGateway (constraint_windows).
"""
from typing import Dict, List, Optional


def active_window(
    env_now: float, start_hour: int, windows: List[Dict]
) -> Optional[Dict]:
    """Return the first window covering the current simulation hour.

    ``env_now`` is seconds since simulation start; ``start_hour`` is the
    wall-clock hour the simulation began at. A window is active when
    start_hour <= hour < end_hour; windows that wrap midnight
    (e.g. 22 to 2) are handled. Returns None when no window matches.
    """
    hour = (int(env_now / 3600) + start_hour) % 24

    for window in windows:
        start = window.get("start_hour", 0)
        end = window.get("end_hour", 0)
        if start <= end:
            if start <= hour < end:
                return window
        else:
            if hour >= start or hour < end:
                return window

    return None
