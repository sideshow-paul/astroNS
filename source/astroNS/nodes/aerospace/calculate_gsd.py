""" Ground Sample Distance (GSD) Calculator Node

This node calculates the Ground Sample Distance (GSD) for a satellite or aerial
imaging system using the formula:

           D * SH
GSD = ---------------
         FL * IH

Where:
GSD = Ground Sample Distance
D   = Distance in km
SH  = Sensor width/height
FL  = Focal length of the camera
IH  = Image width/length

This node can calculate distance either from a direct distance value or
by computing the distance between a source and target in ECEF coordinates.
"""
import datetime
import numpy as np
from math import sqrt

from typing import List, Dict, Tuple, Any, Optional, Callable
from simpy.core import Environment

from nodes.core.base import BaseNode


class CalculateGSD(BaseNode):
    """Ground Sample Distance Calculator Node

    Calculates the GSD for a satellite or aerial imaging system based on the
    altitude of the platform, the sensor characteristics, and the camera parameters.

    Configuration parameters:
    - distance_key: Key in the input message containing distance in km (default: "distance_km")
    - source_pos_key: Key for source position in ECEF km (default: "source_pos_ecef_km")
    - target_pos_key: Key for target position in ECEF km (default: "target_pos_ecef_km")
    - use_ecef_positions: If True, calculate distance from ECEF positions (default: False)
    - sensor_height_key: Key for sensor height in mm (default: "sensor_height_mm")
    - sensor_width_key: Key for sensor width in mm (default: "sensor_width_mm")
    - focal_length_key: Key for focal length in mm (default: "focal_length_mm")
    - image_height_key: Key for image height in pixels (default: "image_height_px")
    - image_width_key: Key for image width in pixels (default: "image_width_px")
    - use_sensor_height: If True, use sensor height, otherwise use width (default: True)
    - gsd_storage_key: Key to store the calculated GSD value (default: "gsd_m_per_px")
    - time_processing: Processing time in simulation (default: 0.0)
    - time_delay: Message delay time in simulation (default: 0.0)
    """

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize GSD Calculator node"""
        super().__init__(env, name, configuration, self.execute())

        # Node Reserve Time
        self._processing_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_processing", 0.0
        )
        # Message Delay Time
        self._time_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_delay", 0.0
        )

        # Configuration parameters
        self._distance_key = self.setStringFromConfig("distance_key", "distance_km")
        self._source_pos_key = self.setStringFromConfig("source_pos_key", "source_pos_ecef_km")
        self._target_pos_key = self.setStringFromConfig("target_pos_key", "target_pos_ecef_km")
        self._use_ecef_positions = self.setBoolFromConfig("use_ecef_positions", False)
        self._sensor_height_key = self.setStringFromConfig("sensor_height_key", "sensor_height_mm")
        self._sensor_width_key = self.setStringFromConfig("sensor_width_key", "sensor_width_mm")
        self._focal_length_key = self.setStringFromConfig("focal_length_key", "focal_length_mm")
        self._image_height_key = self.setStringFromConfig("image_height_key", "image_height_px")
        self._image_width_key = self.setStringFromConfig("image_width_key", "image_width_px")
        self._use_sensor_height = self.setBoolFromConfig("use_sensor_height", True)
        self._gsd_storage_key = self.setStringFromConfig("gsd_storage_key", "gsd_m_per_px")
        self._geometry_results_key = self.setStringFromConfig("geometry_results_key", "geometry_results")

        # Default values for direct configuration
        self._distance_km = self.setFloatFromConfig("distance_km", 0.0)
        self._sensor_height_mm = self.setFloatFromConfig("sensor_height_mm", 0.0)
        self._sensor_width_mm = self.setFloatFromConfig("sensor_width_mm", 0.0)
        self._focal_length_mm = self.setFloatFromConfig("focal_length_mm", 0.0)
        self._image_height_px = self.setFloatFromConfig("image_height_px", 0.0)
        self._image_width_px = self.setFloatFromConfig("image_width_px", 0.0)

        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        return self._time_delay()

    @property
    def gsd_storage_key(self) -> Optional[str]:
        return self._gsd_storage_key()

    @property
    def distance_key(self) -> Optional[str]:
        return self._distance_key()

    @property
    def source_pos_key(self) -> Optional[str]:
        return self._source_pos_key()

    @property
    def target_pos_key(self) -> Optional[str]:
        return self._target_pos_key()

    @property
    def use_ecef_positions(self) -> bool:
        return self._use_ecef_positions()

    @property
    def use_sensor_height(self) -> bool:
        return self._use_sensor_height()

    @property
    def geometry_results_key(self) -> Optional[str]:
        return self._geometry_results_key()

    def calculate_distance_km(self, source_pos: List[float], target_pos: List[float]) -> float:
        """
        Calculate the distance between two points in ECEF coordinates.

        Args:
            source_pos: Source position [x, y, z] in ECEF km
            target_pos: Target position [x, y, z] in ECEF km

        Returns:
            Distance in kilometers
        """
        if len(source_pos) < 3 or len(target_pos) < 3:
            return 0.0

        dx = source_pos[0] - target_pos[0]
        dy = source_pos[1] - target_pos[1]
        dz = source_pos[2] - target_pos[2]

        return sqrt(dx*dx + dy*dy + dz*dz)

    def calculate_gsd(self,
                     distance_km: float,
                     sensor_size_mm: float,
                     focal_length_mm: float,
                     image_size_px: float) -> float:
        """
        Calculate the Ground Sample Distance.

        Args:
            distance_km: Distance in kilometers
            sensor_size_mm: Sensor size (height or width) in millimeters
            focal_length_mm: Focal length in millimeters
            image_size_px: Image size (height or width) in pixels

        Returns:
            Ground Sample Distance in meters per pixel
        """
        # Convert distance to millimeters for consistent units
        distance_mm = distance_km * 1000000.0  # 1km = 1,000,000mm

        # Handle division by zero
        if focal_length_mm <= 0 or image_size_px <= 0:
            return 0.0

        # Calculate GSD in millimeters per pixel
        gsd_mm_per_px = (distance_mm * sensor_size_mm) / (focal_length_mm * image_size_px)

        # Convert back to meters per pixel
        gsd_m_per_px = gsd_mm_per_px / 1000.0

        return gsd_m_per_px

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

                # Check if geometry_results exist and use them
                geometry_results = msg.get(self.geometry_results_key, None)
                distance_km = msg.get(self.distance_key, self._distance_km())

                if geometry_results and isinstance(geometry_results, list) and len(geometry_results) > 0:
                    # Use the first geometry result for GSD calculation
                    geometry_data = geometry_results[0]

                    # Extract distance from geometry results
                    if 'distance_km' in geometry_data:
                        distance_km = geometry_data['distance_km']
                        msg[self.distance_key] = distance_km

                    # Extract ECEF positions if available
                    if 'observer_position_ecef_km' in geometry_data and 'target_position_ecef_km' in geometry_data:
                        msg[self.source_pos_key] = geometry_data['observer_position_ecef_km']
                        msg[self.target_pos_key] = geometry_data['target_position_ecef_km']

                # If using ECEF positions, calculate distance from positions
                elif self.use_ecef_positions:
                    source_pos = msg.get(self.source_pos_key, None)
                    target_pos = msg.get(self.target_pos_key, None)

                    if source_pos and target_pos:
                        calculated_distance = self.calculate_distance_km(source_pos, target_pos)
                        # Only override if we got a valid calculation
                        if calculated_distance > 0:
                            distance_km = calculated_distance
                            # Store the calculated distance in the message
                            msg[self.distance_key] = distance_km

                sensor_height_mm = msg.get(self._sensor_height_key(), self._sensor_height_mm())
                sensor_width_mm = msg.get(self._sensor_width_key(), self._sensor_width_mm())
                focal_length_mm = msg.get(self._focal_length_key(), self._focal_length_mm())
                image_height_px = msg.get(self._image_height_key(), self._image_height_px())
                image_width_px = msg.get(self._image_width_key(), self._image_width_px())

                # Determine which sensor dimension to use (height or width)
                if self.use_sensor_height:
                    sensor_size_mm = sensor_height_mm
                    image_size_px = image_height_px
                else:
                    sensor_size_mm = sensor_width_mm
                    image_size_px = image_width_px

                # Calculate GSD
                gsd_m_per_px = self.calculate_gsd(
                    distance_km,
                    sensor_size_mm,
                    focal_length_mm,
                    image_size_px
                )

                # Store the result in the message
                msg[self.gsd_storage_key] = gsd_m_per_px

                # Log the calculation
                data_source = "geometry_results" if geometry_results else "direct/ECEF"
                print(
                    self.log_prefix(msg.get("ID", "unknown"))
                    + f"Calculated GSD: {gsd_m_per_px:.6f} m/px (Distance: {distance_km:.2f}km, "
                    + f"Sensor: {sensor_size_mm:.2f}mm, FL: {focal_length_mm:.2f}mm, "
                    + f"Image: {image_size_px:.0f}px) [Source: {data_source}]"
                )

                processing_time = self._processing_delay()
                data_out_list = [msg]
            else:
                data_out_list = []
