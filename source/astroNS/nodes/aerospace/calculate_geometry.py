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
import sys
import os
from math import degrees, radians

from typing import List, Dict, Tuple, Any, Optional, Callable
from simpy.core import Environment
from datetime import datetime, timedelta, timezone

# Add simple_accgen to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../simple_accgen/src'))

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
        self._satellite_name = self.setStringFromConfig('satellite_name', 'ISS')
        self._satellite_name_key = self.setStringFromConfig('satellite_name_key', 'satellite_name')
        self._tle_file_path = self.setStringFromConfig('tle_file_path', 'satellites.json')

        self._target_lat_key = self.setStringFromConfig('target_lat_key', 'target_lat')
        self._target_lon_key = self.setStringFromConfig('target_lon_key', 'target_lon')
        self._target_alt_key = self.setStringFromConfig('target_alt_key', 'target_alt')

        self._parameters_key = self.setStringFromConfig('parameters_key', '')

        if self._parameters_key:
            self._parameters = configuration.get(self._parameters_key, {})
            self._target_lat = self._parameters.get(self._target_lat_key, 0.0)
            self._target_lon = self._parameters.get(self._target_lon_key, 0.0)
            self._target_alt = self._parameters.get(self._target_alt_key, 0.0)
        else:
            self._target_lat = self.setFloatFromConfig(self._target_lat_key, 0.0)
            self._target_lon = self.setFloatFromConfig(self._target_lon_key, 0.0)
            self._target_alt = self.setFloatFromConfig(self._target_alt_key, 0.0)

        self._start_time_key = self.setStringFromConfig('start_time_key', 'start_time')

        # Default values for direct configuration

        self._start_time_str = self.setStringFromConfig('start_time', datetime.now(timezone.utc).isoformat())
        self._duration_seconds = self.setFloatFromConfig('duration_seconds', 3600.0)  # Default to 1 hour
        self._step_seconds = self.setFloatFromConfig('step_seconds', 60.0)  # Default to 1 minute steps
        self._storage_key = self.setStringFromConfig('storage_key', 'geometry_results')
        self._single_time_point = self.setBoolFromConfig('single_time_point', False)

        # Load TLE data from file
        self.tle_data = self._load_tle_data()

        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        return self._time_delay()

    @property
    def storage_key(self) -> Optional[str]:
        return self._storage_key()

    def _load_tle_data(self) -> Dict[str, Dict[str, str]]:
        """
        Load TLE data from JSON file.

        Returns:
            Dictionary mapping satellite names to TLE data
        """
        import json
        import os

        try:
            tle_file = self._tle_file_path()

            # Check if file exists in multiple possible locations
            possible_paths = [
                tle_file,
                os.path.join(os.path.dirname(__file__), tle_file),
                os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', tle_file),
                os.path.join(os.getcwd(), tle_file)
            ]

            tle_data = {}
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        tle_data = json.load(f)
                    self.logger.info(f"Loaded TLE data from: {path}")
                    break
            else:
                # If no file found, create default TLE data
                self.logger.warning(f"TLE file not found at any location. Using default ISS TLE data.")
                tle_data = {
                    "ISS": {
                        "tle_line1": "1 25544U 98067A   25096.03700594  .00015269  00000+0  28194-3 0  9999",
                        "tle_line2": "2 25544  51.6369 304.3678 0004922  13.5339 346.5781 15.49280872503978"
                    }
                }

            return tle_data

        except Exception as e:
            self.logger.error(f"Error loading TLE data: {e}")
            # Return default ISS TLE data as fallback
            return {
                "ISS": {
                    "tle_line1": "1 25544U 98067A   25096.03700594  .00015269  00000+0  28194-3 0  9999",
                    "tle_line2": "2 25544  51.6369 304.3678 0004922  13.5339 346.5781 15.49280872503978"
                }
            }

    def _get_tle_for_satellite(self, satellite_name: str) -> Tuple[str, str]:
        """
        Get TLE lines for a given satellite name.

        Args:
            satellite_name: Name of the satellite

        Returns:
            Tuple of (tle_line1, tle_line2)
        """
        if satellite_name in self.tle_data:
            tle_info = self.tle_data[satellite_name]
            return tle_info.get('tle_line1', ''), tle_info.get('tle_line2', '')
        else:
            self.logger.warning(f"Satellite '{satellite_name}' not found in TLE data. Using ISS as fallback.")
            if 'ISS' in self.tle_data:
                tle_info = self.tle_data['ISS']
                return tle_info.get('tle_line1', ''), tle_info.get('tle_line2', '')
            else:
                # Last resort fallback
                return ("1 25544U 98067A   25096.03700594  .00015269  00000+0  28194-3 0  9999",
                        "2 25544  51.6369 304.3678 0004922  13.5339 346.5781 15.49280872503978")

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
                satellite_name = msg.get(self._satellite_name_key(), self._satellite_name())
                tle_line1, tle_line2 = self._get_tle_for_satellite(satellite_name)
                target_lat = msg.get(self._target_lat_key(), self._target_lat)
                target_lon = msg.get(self._target_lon_key(), self._target_lon)
                target_alt = msg.get(self._target_alt_key(), self._target_alt)
                start_time_str = msg.get(self._start_time_key(), self._start_time_str())
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

                    msg['geo_polygon'] = [ [target_lat+0.1, target_lon], [target_lat, target_lon+0.1], [target_lat-0.1, target_lon], [target_lat, target_lon-0.1]]

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
