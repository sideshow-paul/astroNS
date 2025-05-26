from typing import List, Dict, Tuple, Any, Optional, Callable
from datetime import datetime, timedelta, timezone
import numpy as np
import logging
import sys
import os

# Add simple_accgen to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../simple_accgen/src'))

from nodes.core.base import BaseNode
from simple_accgen.access_generator import AccessGenerator as SimpleAccessGenerator
from simple_accgen.access_generator import GrazingAngleFilter, TargetSunElevationAngleFilter
from simple_accgen.geometry import ObserverTargetGeometry
from simple_accgen.propagation.statevector_provider import GeodeticPoint, TLEStateVectorProvider

class AccessGenerator(BaseNode):
    """
    Node that generates satellite access periods to ground targets using the simple-accgen library.

    Configuration parameters:
    - tle_line1: First line of the TLE
    - tle_line2: Second line of the TLE
    - target_lat: Target latitude in degrees
    - target_lon: Target longitude in degrees
    - target_alt: Target altitude in meters
    - start_time: Start time of the analysis (ISO format with timezone)
    - duration_seconds: Duration of the analysis in seconds
    - step_seconds: Time step for analysis in seconds
    - min_grazing_angle: Minimum grazing angle in degrees (default: 10)
    - sun_min_angle: Minimum sun elevation angle in degrees (default: -90)
    - sun_max_angle: Maximum sun elevation angle in degrees (default: 0)
    """

    def __init__(self, env, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        # Initialize logger
        self.logger = logging.getLogger(f"{self.__class__.__name__}_{name}")

        # Node Reserve Time
        self._processing_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_processing", 0.0
        )
        # Message Delay Time
        self._time_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_delay", 0.0
        )

        # Initialize configuration parameters
        self._tle_line1 = self.setStringFromConfig('tle_line1', '')
        self._tle_line2 = self.setStringFromConfig('tle_line2', '')
        self._target_lat = self.setFloatFromConfig('target_lat', 0.0)
        self._target_lon = self.setFloatFromConfig('target_lon', 0.0)
        self._target_alt = self.setFloatFromConfig('target_alt', 0.0)
        self._start_time_str = self.setStringFromConfig('start_time', datetime.now(timezone.utc).isoformat())
        self._duration_seconds = self.setFloatFromConfig('duration_seconds', 86400.0)  # Default to 1 day
        self._step_seconds = self.setFloatFromConfig('step_seconds', 1.0)  # Default to 1 second steps
        self._min_grazing_angle = self.setFloatFromConfig('min_grazing_angle', 10.0)
        self._sun_min_angle = self.setFloatFromConfig('sun_min_angle', -90.0)
        self._sun_max_angle = self.setFloatFromConfig('sun_max_angle', 0.0)
        self._storage_key = self.setStringFromConfig('storage_key', 'Access_Results')

        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        return self._time_delay()

    @property
    def storage_key(self) -> Optional[str]:
        return self._storage_key()

    def execute(self):
        """Simpy execution code"""
        delay: float = 0.0
        processing_time: float = delay
        data_out_list: List[Tuple] = []
        while True:
            data_in = yield (delay, processing_time, data_out_list)

            if data_in:
                msg = data_in.copy()
                delay = self.time_delay

                # Get configuration values from input or defaults
                tle_line1 = msg.get('tle_line1', self._tle_line1())
                tle_line2 = msg.get('tle_line2', self._tle_line2())
                target_lat = msg.get('target_lat', self._target_lat())
                target_lon = msg.get('target_lon', self._target_lon())
                target_alt = msg.get('target_alt', self._target_alt())
                start_time_str = msg.get('start_time', self._start_time_str())
                duration_seconds = msg.get('duration_seconds', self._duration_seconds())
                step_seconds = msg.get('step_seconds', self._step_seconds())
                min_grazing_angle = msg.get('min_grazing_angle', self._min_grazing_angle())
                sun_min_angle = msg.get('sun_min_angle', self._sun_min_angle())
                sun_max_angle = msg.get('sun_max_angle', self._sun_max_angle())

                try:
                    # Create satellite state vector provider from TLE
                    satellite = TLEStateVectorProvider(tle_line1, tle_line2)

                    # Create target point
                    target = GeodeticPoint.createFromLatLonAlt(target_lat, target_lon, target_alt)

                    # Generate time points for analysis
                    start = datetime.fromisoformat(start_time_str)
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)

                    times = [start + timedelta(seconds=dt) for dt in range(0, int(duration_seconds), int(step_seconds))]

                    # Create geometry object
                    geometry = ObserverTargetGeometry.create(satellite, target, times)

                    # Create access generator
                    access_gen = SimpleAccessGenerator(geometry)

                    # Add filters
                    access_gen.add_filter(GrazingAngleFilter(min_angle=min_grazing_angle, degrees=True))
                    access_gen.add_filter(TargetSunElevationAngleFilter(
                        min_angle=sun_min_angle, max_angle=sun_max_angle, degrees=True))

                    # Generate access regions
                    regions = access_gen.generate_access_regions()

                    # Get access timestamps
                    access_times = access_gen.get_access_timestamps(regions)

                    # Calculate stats for each access
                    access_results = []
                    for i, (start_time, end_time) in enumerate(access_times):
                        start_idx, end_idx = regions[i]

                        # Calculate grazing angle stats
                        region_grazes = np.degrees(geometry.grazing_angle[start_idx:end_idx+1])
                        min_graze = np.min(region_grazes)
                        max_graze = np.max(region_grazes)
                        avg_graze = np.mean(region_grazes)

                        # Calculate sun elevation angle stats
                        region_suns = np.degrees(geometry.sun_elevation_angle[start_idx:end_idx+1])
                        min_sun = np.min(region_suns)
                        max_sun = np.max(region_suns)
                        avg_sun = np.mean(region_suns)

                        # Duration in seconds
                        duration = (end_time - start_time).total_seconds()

                        # Create access result
                        access_result = {
                            'access_id': i + 1,
                            'start_time': start_time.isoformat(),
                            'end_time': end_time.isoformat(),
                            'duration_seconds': duration,
                            'grazing_angle': {
                                'min': float(min_graze),
                                'max': float(max_graze),
                                'avg': float(avg_graze)
                            },
                            'sun_elevation': {
                                'min': float(min_sun),
                                'max': float(max_sun),
                                'avg': float(avg_sun)
                            }
                        }

                        access_results.append(access_result)

                    # Store access results in message
                    msg[self.storage_key] = access_results

                    print(
                        self.log_prefix(msg.get("ID", "unknown"))
                        + f"Generated {len(access_results)} access periods at {self.env.now}"
                    )

                except Exception as e:
                    self.logger.error(f"Error generating access: {e}")
                    msg[self.storage_key] = []

                processing_time = self._processing_delay()
                data_out_list = [msg]
            else:
                data_out_list = []
