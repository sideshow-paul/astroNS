""" Satellite-Target Geometry Calculator Node

This node calculates various geometric properties between a satellite (observer)
and a ground target using the simple-accgen library's ObserverTargetGeometry class.

Calculated properties include:
- Grazing angle
- Observer-target distance
- Azimuth and elevation angles
- Sun elevation angle at target
- And more
"""
import datetime
import numpy as np
import logging
from math import degrees, radians

from typing import List, Dict, Tuple, Any, Optional, Callable
from simpy.core import Environment
from datetime import datetime, timedelta, timezone

from nodes.core.base import BaseNode
from simple_accgen.geometry import ObserverTargetGeometry
from simple_accgen.propagation.statevector_provider import (
    GeodeticPoint, TLEStateVectorProvider, CoordinateFrame, SunStateVectorProvider
)


class CalculateGeometry(BaseNode):
    """Satellite-Target Geometry Calculator Node

    Calculates geometric properties between a satellite (observer) and a ground target
    at a specific time or range of times.

    Configuration parameters:
    - tle_line1: First line of the TLE
    - tle_line2: Second line of the TLE
    - target_lat: Target latitude in degrees
    - target_lon: Target longitude in degrees
    - target_alt: Target altitude in meters (default: 0.0)
    - start_time: Start time of the analysis (ISO format with timezone)
    - duration_seconds: Duration of the analysis in seconds (default: 3600, 1 hour)
    - step_seconds: Time step for analysis in seconds (default: 60, 1 minute)
    - storage_key: Key to store the calculated geometry results (default: "geometry_results")
    - time_processing: Processing time in simulation (default: 0.0)
    - time_delay: Message delay time in simulation (default: 0.0)
    """

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize Geometry Calculator node"""
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

        # Configuration parameters
        self._tle_line1 = self.setStringFromConfig('tle_line1', '')
        self._tle_line2 = self.setStringFromConfig('tle_line2', '')
        self._target_lat = self.setFloatFromConfig('target_lat', 0.0)
        self._target_lon = self.setFloatFromConfig('target_lon', 0.0)
        self._target_alt = self.setFloatFromConfig('target_alt', 0.0)
        self._start_time_str = self.setStringFromConfig('start_time', datetime.now(timezone.utc).isoformat())
        self._duration_seconds = self.setFloatFromConfig('duration_seconds', 3600.0)  # Default to 1 hour
        self._step_seconds = self.setFloatFromConfig('step_seconds', 60.0)  # Default to 1 minute steps
        self._storage_key = self.setStringFromConfig('storage_key', 'geometry_results')
        self._single_time_point = self.setBoolFromConfig('single_time_point', False)

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
                single_time_point = msg.get('single_time_point', self._single_time_point())

                try:
                    # Create satellite state vector provider from TLE
                    satellite = TLEStateVectorProvider(tle_line1, tle_line2)

                    # Create target point
                    target = GeodeticPoint.createFromLatLonAlt(target_lat, target_lon, target_alt)

                    # Parse start time
                    start = datetime.fromisoformat(start_time_str)
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)

                    # Generate time points for analysis
                    if single_time_point:
                        times = [start]
                    else:
                        times = [start + timedelta(seconds=dt) for dt in range(0, int(duration_seconds), int(step_seconds))]

                    # Create geometry object
                    geometry = ObserverTargetGeometry.create(satellite, target, times)

                    # Process geometry data
                    geometry_results = self.process_geometry_data(geometry, times)

                    # Store geometry results in message
                    msg[self.storage_key] = geometry_results

                    print(
                        self.log_prefix(msg.get("ID", "unknown"))
                        + f"Calculated geometry for {len(times)} time points at {self.env.now}"
                    )

                except Exception as e:
                    self.logger.error(f"Error calculating geometry: {e}")
                    msg[self.storage_key] = []

                processing_time = self._processing_delay()
                data_out_list = [msg]
            else:
                data_out_list = []

    def process_geometry_data(self, geometry: ObserverTargetGeometry, times: List[datetime]) -> List[Dict[str, Any]]:
        """
        Process and extract useful data from the geometry object.

        Args:
            geometry: The ObserverTargetGeometry object
            times: List of time points

        Returns:
            List of dictionaries containing geometric properties at each time point
        """
        results = []

        # Extract key arrays from geometry
        grazing_angles = np.degrees(geometry.grazing_angle)
        distances = geometry.distance
        azimuths = np.degrees(geometry.azimuth)
        elevations = np.degrees(geometry.elevation)
        sun_elevations = np.degrees(geometry.sun_elevation_angle)

        # Get observer and target positions
        observer_positions_ecef = geometry.observer_positions_ecef
        target_positions_ecef = geometry.target_positions_ecef

        # Process each time point
        for i in range(len(times)):
            # Skip invalid data points (e.g., where sun elevation calculation failed)
            if np.isnan(grazing_angles[i]) or np.isnan(sun_elevations[i]):
                continue

            # Create result for this time point
            time_result = {
                'time': times[i].isoformat(),
                'grazing_angle_deg': float(grazing_angles[i]),
                'distance_km': float(distances[i]),
                'azimuth_deg': float(azimuths[i]),
                'elevation_deg': float(elevations[i]),
                'sun_elevation_deg': float(sun_elevations[i]),
                'observer_position_ecef_km': observer_positions_ecef[i].tolist(),
                'target_position_ecef_km': target_positions_ecef[i].tolist(),
            }

            # Add derived calculations

            # Visibility status (simple check - needs elevation above horizon)
            time_result['is_visible'] = elevations[i] > 0

            # Day/night status at target (simple check based on sun elevation)
            time_result['is_day'] = sun_elevations[i] > 0

            # Check if in eclipse (simplified method)
            time_result['is_in_eclipse'] = self.check_eclipse(
                observer_positions_ecef[i],
                sun_elevations[i]
            )

            results.append(time_result)

        return results

    def check_eclipse(self, satellite_position_ecef: np.ndarray, sun_elevation: float) -> bool:
        """
        Simplified check if satellite is in Earth's shadow.
        More precise methods require additional calculations.

        Args:
            satellite_position_ecef: Satellite position in ECEF frame
            sun_elevation: Sun elevation angle in degrees

        Returns:
            True if satellite is likely in eclipse
        """
        # This is a very simplified approach
        # A more accurate calculation would check if the Earth is between
        # the satellite and the Sun

        # Get satellite distance from Earth center
        satellite_distance = np.linalg.norm(satellite_position_ecef)

        # Earth radius in km
        earth_radius = 6378.0

        # If satellite is on night side and close enough to Earth
        if sun_elevation < -1 and satellite_distance < earth_radius * 3:
            # Simple geometric check - this is approximate
            return True

        return False
