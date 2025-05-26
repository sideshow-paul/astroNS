from dataclasses import dataclass
from functools import cached_property
from typing import List, Union, Tuple
from datetime import datetime
import numpy as np
import numba

from simple_accgen.constants import WGS84_A, WGS84_F
from simple_accgen.propagation.conversions import itrs2geodetic
from simple_accgen.propagation.statevector_provider import CoordinateFrame, StateVectorProvider, SunStateVectorProvider

@numba.njit(parallel=True)
def calculate_zeniths(lat_rad, lon_rad):
    """
    Calculate zenith vectors (unit vectors pointing perpendicular to the reference ellipsoid) 
    for given positions using the WGS84 ellipsoid model.
    
    Parameters:
    -----------
    lat_rad : np.ndarray
        Array of shape (n,) containing latitudes in radians
    lon_rad : np.ndarray
        Array of shape (n,) containing longitudes in radians
        
    Returns:
    --------
    np.ndarray
        Array of shape (n, 3) containing the zenith unit vectors in ECEF frame
    """
    n = lat_rad.shape[0]
    zeniths = np.empty((n, 3), dtype=np.float64)
    
    # WGS84 parameters
    f = WGS84_F  # flattening
    e2 = 2*f - f*f  # eccentricity squared
    
    for i in numba.prange(n):
        # For an ellipsoid, the normal vector components
        zeniths[i, 0] = np.cos(lat_rad[i]) * np.cos(lon_rad[i])
        zeniths[i, 1] = np.cos(lat_rad[i]) * np.sin(lon_rad[i])
        # This is where the correction for the ellipsoid comes in:
        zeniths[i, 2] = np.sin(lat_rad[i]) * (1 - e2)
        
        # Normalize the vector to ensure it's a unit vector
        magnitude = np.sqrt(zeniths[i, 0]**2 + zeniths[i, 1]**2 + zeniths[i, 2]**2)
        zeniths[i, 0] /= magnitude
        zeniths[i, 1] /= magnitude
        zeniths[i, 2] /= magnitude
        
    return zeniths

# Numba-optimized function for distance calculation
@numba.njit(parallel=True)
def calculate_ranges(observer_positions, target_positions):
    """
    Calculate ranges between observer and target positions using Numba for acceleration.
    
    Parameters:
    -----------
    observer_positions : np.ndarray
        Array of shape (n, 3) containing observer positions
    target_positions : np.ndarray
        Array of shape (n, 3) containing target positions
        
    Returns:
    --------
    np.ndarray
        Array of shape (n,) containing the ranges
    """
    n = observer_positions.shape[0]
    ranges = np.empty(n, dtype=np.float64)
    
    for i in numba.prange(n):
        delta_x = target_positions[i, 0] - observer_positions[i, 0]
        delta_y = target_positions[i, 1] - observer_positions[i, 1]
        delta_z = target_positions[i, 2] - observer_positions[i, 2]
        ranges[i] = np.sqrt(delta_x**2 + delta_y**2 + delta_z**2)
        
    return ranges

@numba.njit(parallel=True)
def calculate_grazes(observer_positions, target_positions, target_zeniths):
    """
    Calculate grazing angles for observer-target geometries.
    
    The grazing angle is defined as 90° minus the angle between:
    1. The line-of-sight vector from target to observer
    2. The local zenith vector at the target position
    
    Parameters:
    -----------
    observer_positions : np.ndarray
        Array of shape (n, 3) containing observer positions in ECEF (km)
    target_positions : np.ndarray
        Array of shape (n, 3) containing target positions in ECEF (km)
    target_zeniths : np.ndarray
        Array of shape (n, 3) containing zenith unit vectors at target locations
        
    Returns:
    --------
    np.ndarray
        Array of shape (n,) containing grazing angles in radians
    """
    n = observer_positions.shape[0]
    grazing_angles = np.empty(n, dtype=np.float64)
    
    for i in numba.prange(n):
        # Get target position (on or near Earth's surface)
        target_pos = target_positions[i]
        
        # Use the provided correct zenith vector
        target_zenith = target_zeniths[i]
        
        # Calculate line-of-sight vector from target to observer
        los_vector = observer_positions[i] - target_pos
        los_unit = los_vector / np.linalg.norm(los_vector)
        
        # Calculate the angle between LOS and zenith using dot product
        cos_angle = np.dot(los_unit, target_zenith)
        
        # Ensure cos_angle is within valid range [-1, 1] to avoid numerical issues
        cos_angle = max(-1.0, min(1.0, cos_angle))
        
        # Angle between vectors
        angle = np.arccos(cos_angle)
        
        # Grazing angle = 90° - angle between LOS and zenith
        # π/2 radians = 90 degrees
        grazing_angles[i] = np.pi/2 - angle
    
    return grazing_angles

@dataclass
class ObserverTargetGeometry:
    """
    Represents the geometric relationship between an observer and a target over a range of times
    
    All positions, velocities, and vectors are in ECEF unless otherwise specified
    Distances in km, angles in radians unless otherwise specified.
    """
    # Core positional data
    observer_position: np.ndarray  # [num_times, 3] position of observer
    observer_velocity: np.ndarray  # [num_times, 3] velocity of observer
    target_position: np.ndarray    # [num_times, 3] position of target
    target_velocity: np.ndarray    # [num_times, 3] velocity of target (I fixed the duplicate field name)
    timestamps: List[datetime]     # List of datetime objects
    frame: CoordinateFrame         # coordinate frame
    
    def __post_init__(self):
        """Validate inputs and ensure shapes are consistent."""
        # Get the number of time steps
        num_times = len(self.timestamps)

        if self.frame != CoordinateFrame.ITRS:
            raise ValueError(f"frame was {self.frame}, must be ITRS")
        
        # Validate that all arrays have the same first dimension
        for name, arr in [
            ("observer_position", self.observer_position),
            ("observer_velocity", self.observer_velocity),
            ("target_position", self.target_position),
            ("target_velocity", self.target_velocity)
        ]:
            if arr.shape[0] != num_times:
                raise ValueError(f"{name} has {arr.shape[0]} time steps, expected {num_times}")
            
            if arr.shape[1] != 3:
                raise ValueError(f"{name} should have shape ({num_times}, 3), got {arr.shape}")
            
    @cached_property
    def target_lla_rad(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        return itrs2geodetic(self.target_position, degrees=False)
    
    @cached_property
    def target_zenith(self) -> np.ndarray:
        """
        Calculate the local zenith vectors at target locations.
        These are unit vectors perpendicular to the reference ellipsoid at each target point.
        
        Returns:
            np.ndarray: Array of zenith vectors, shape (num_times, 3)
        """
        lat, lon, _ = self.target_lla_rad
        return calculate_zeniths(lat, lon)

    
    @cached_property
    def range(self) -> np.ndarray:
        """
        Calculate the range (distance) between observer and target for all timestamps.
        
        Returns:
            np.ndarray: Array of ranges in km, shape (num_times,)
        """
        # Calculate difference vectors for all time steps at once
        delta = self.target_position - self.observer_position
        
        # Calculate the Euclidean norm (L2 norm) along axis 1 (the xyz components)
        # This computes the range for all time steps in a single vectorized operation
        ranges = np.linalg.norm(delta, axis=1)
        
        return ranges
    
    @cached_property
    def grazing_angle(self) -> np.ndarray:
        """
        Calculate the grazing angle between observer and target for all timestamps.
        Uses Numba for accelerated computation.
        
        Returns:
            np.ndarray: Array of grazing angles in radians, shape (num_times,)
        """
        return calculate_grazes(self.observer_position, self.target_position, self.target_zenith)
    
    @cached_property
    def sun_elevation_angle(self) -> np.ndarray:
        """
        Calculate the sun elevation angle at the target position for all timestamps.
        The sun elevation angle is the angle between:
        1. The local horizon at the target position
        2. The line-of-sight vector from the target to the sun
        
        Returns:
            np.ndarray: Array of sun elevation angles in radians, shape (num_times,)
        """
        # Get sun position in ITRS frame
        sun = SunStateVectorProvider()
        sun_positions, _ = sun.getStateVectors(self.timestamps, CoordinateFrame.ITRS)
        
        # Calculate elevation angles using numba-accelerated function
        return calculate_grazes(sun_positions, self.target_position, self.target_zenith)
    
    @classmethod
    def create(cls, 
               observer: StateVectorProvider, 
               target: StateVectorProvider, 
               times: Union[datetime, List[datetime]],
               frame: CoordinateFrame = CoordinateFrame.ITRS) -> 'ObserverTargetGeometry':
        """
        Create geometry object from two objects implementing the StateVectorProvider interface.
        
        Parameters:
        -----------
        observer : StateVectorProvider
            Object providing observer state vectors
        target : StateVectorProvider
            Object providing target state vectors
        times : datetime or List[datetime]
            Times for which to compute the geometry
        frame : CoordinateFrame, optional
            Coordinate frame for calculations, default is ITRS
            
        Returns:
        --------
        ObserverTargetGeometry
            New geometry object with state vectors from the provided objects
        """
        # Get state vectors for observer
        obs_positions, obs_velocities = observer.getStateVectors(times, frame)
        
        # Get state vectors for target
        tar_positions, tar_velocities = target.getStateVectors(times, frame)
        
        # Convert times to standard datetime list if needed
        if not isinstance(times, list):
            times = [times]
            
        # Create and return the geometry object
        return cls(
            observer_position=obs_positions,
            observer_velocity=obs_velocities,
            target_position=tar_positions,
            target_velocity=tar_velocities,
            timestamps=times,
            frame=frame
        )