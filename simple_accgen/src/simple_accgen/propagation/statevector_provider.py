from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, OrderedDict, Union, List, Tuple, Optional
import numba
import numpy as np
from astropy.time import Time
from astropy.coordinates import get_sun
from enum import Enum
import threading
import logging
from scipy.interpolate import CubicSpline

logger = logging.getLogger(__name__)


from simple_accgen.propagation.conversions import geodetic2itrs, teme_to_gcrs, teme_to_itrs
from simple_accgen.propagation.propagation import generate_satellite_states

class CoordinateFrame(Enum):
    """Enum for supported coordinate frames."""
    TEME = "TEME"  # True Equator Mean Equinox (SGP4 native)
    ITRS = "ITRS"  # International Terrestrial Reference System (ECEF)
    GCRS = "GCRS"  # Geocentric Celestial Reference System (close to J2000)

class StateVectorProvider(ABC):
    @abstractmethod
    def getStateVectors(self, 
                        times: Union[datetime, List[datetime]], 
                        frame: CoordinateFrame = CoordinateFrame.TEME) -> Tuple[Time, np.ndarray, np.ndarray]:
        """
        Get satellite state vectors for specified time(s) in the requested coordinate frame.
        
        Parameters:
        -----------
        times : datetime or List[datetime]
            Single datetime or list of datetimes for which to provide state vectors
        frame : CoordinateFrame, optional
            Coordinate frame for the output vectors, default is TEME
            
        Returns:
        --------
        tuple
            (times, positions, velocities) where:
            - times is an array of astropy Time objects
            - positions is a numpy array of shape (n, 3) in km
            - velocities is a numpy array of shape (n, 3) in km/s
        """
        pass


class TLEStateVectorProvider(StateVectorProvider):

    def __init__(self, tle_line1: str, tle_line2: str):
        """
        Initialize the TLE-based state vector provider.
        
        Parameters:
        -----------
        tle_line1 : str
            First line of the TLE
        tle_line2 : str
            Second line of the TLE
        """
        self.tle_line1 = tle_line1
        self.tle_line2 = tle_line2
    
    def getStateVectors(self, 
                        times: Union[datetime, List[datetime]], 
                        frame: CoordinateFrame = CoordinateFrame.TEME) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get satellite state vectors for the specified time(s) using TLE propagation.
        
        Parameters:
        -----------
        times : datetime or List[datetime]
            Single datetime or list of datetimes for which to provide state vectors
        frame : CoordinateFrame, optional
            Coordinate frame for the output vectors, default is TEME
            
        Returns:
        --------
        tuple
            (times, positions, velocities) where:
            - times is an array of astropy Time objects
            - positions is a numpy array of shape (n, 3) in km
            - velocities is a numpy array of shape (n, 3) in km/s
        """
        # Handle single datetime
        if isinstance(times, datetime):
            times = [times]
        
        if not times:
            return Time([]), np.array([]), np.array([])
        
        # Sort times to ensure they're in chronological order
        times = sorted(times)
        
        # Generate all state vectors within the range (in TEME)
        astropy_times, teme_positions, teme_velocities = generate_satellite_states(
            self.tle_line1, 
            self.tle_line2, 
            times)
        
        # Convert to the requested frame if necessary
        positions = teme_positions
        velocities = teme_velocities
        
        if frame == CoordinateFrame.ITRS:
            positions, velocities = teme_to_itrs(astropy_times, teme_positions, teme_velocities)
        elif frame == CoordinateFrame.GCRS:
            positions, velocities = teme_to_gcrs(astropy_times, teme_positions, teme_velocities)
        # For TEME, we already have the correct values
        
        return positions, velocities
    
@dataclass
class GeodeticPoint(StateVectorProvider):
    positionITRS: np.ndarray
    velocityITRS: Optional[np.ndarray] = None
    
    def getStateVectors(self, 
                        times: Union[datetime, List[datetime]], 
                        frame: CoordinateFrame = CoordinateFrame.TEME) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get state vectors for the geodetic point for specified time(s).
        
        Parameters:
        -----------
        times : datetime or List[datetime]
            Single datetime or list of datetimes for which to provide state vectors
        frame : CoordinateFrame, optional
            Coordinate frame for the output vectors, default is TEME
            
        Returns:
        --------
        tuple
            (times, positions, velocities) where:
            - times is an array of astropy Time objects
            - positions is a numpy array of shape (n, 3) in km
            - velocities is a numpy array of shape (n, 3) in km/s
        """
        # Handle single datetime
        if isinstance(times, datetime):
            times = [times]
        
        if not times:
            return Time([]), np.array([]), np.array([])
        
        # Sort times to ensure they're in chronological order
        times = sorted(times)
        astropy_times = Time(times)
        
        # Create arrays of positions and velocities
        n_times = len(times)
        
        # For a geodetic point, the position in ITRS is constant
        positions_itrs = np.tile(self.positionITRS, (n_times, 1))
        
        # For velocity, use provided velocity or zeros
        if self.velocityITRS is not None:
            velocities_itrs = np.tile(self.velocityITRS, (n_times, 1))
        else:
            velocities_itrs = np.zeros((n_times, 3))
        
        # Convert to the requested frame if necessary
        if frame == CoordinateFrame.TEME:
            # Need to convert from ITRS to TEME (reverse of teme_to_itrs)
            from simple_accgen.propagation.conversions import itrs_to_teme
            positions, velocities = itrs_to_teme(astropy_times, positions_itrs, velocities_itrs)
        elif frame == CoordinateFrame.GCRS:
            # Convert ITRS to GCRS
            from simple_accgen.propagation.conversions import itrs_to_gcrs
            positions, velocities = itrs_to_gcrs(astropy_times, positions_itrs, velocities_itrs)
        else:  # CoordinateFrame.ITRS
            positions = positions_itrs
            velocities = velocities_itrs
            
        return positions, velocities
    
    @classmethod
    def createFromLatLonAlt(cls, lat_deg: float, lon_deg: float, alt_km: float) -> 'GeodeticPoint':
        """
        Create a GeodeticPoint from latitude, longitude, and altitude.
        
        Parameters:
        -----------
        lat_deg : float
            Latitude in degrees
        lon_deg : float
            Longitude in degrees
        alt_km : float
            Altitude above WGS84 ellipsoid in km
            
        Returns:
        --------
        GeodeticPoint
            Instance with position in ITRS coordinates
        """

        itrs = geodetic2itrs(np.array([float(lat_deg)]), 
                             np.array([float(lon_deg)]), 
                             np.array([float(alt_km)]), degrees=True)
        
        # Return a new instance
        return cls(positionITRS=itrs[0])
    

class CachedSunStateVectorProvider(StateVectorProvider):
    """
    Singleton state vector provider that returns the position and velocity of the Sun
    with caching and cubic spline interpolation.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, max_cache_days: int = 30):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, max_cache_days: int = 7):
        if self._initialized:
            return
            
        self.max_cache_days = max_cache_days
        self.cache_interval_minutes = 2
        self.padding_minutes = 10  # 5 samples on each side
        self.samples_per_day = 24 * 60 // self.cache_interval_minutes  # 720
        
        # Thread-safe LRU cache
        self._cache: Dict[int, Dict] = OrderedDict()
        self._cache_lock = threading.Lock()
        
        self._initialized = True
    
    def _validate_datetime(self, dt: datetime) -> datetime:
        """Ensure datetime is timezone-aware and in UTC."""
        if dt.tzinfo is None:
            # Assume UTC if no timezone is specified
            return dt.replace(tzinfo=timezone.utc)
        elif dt.tzinfo != timezone.utc:
            # Convert to UTC if in different timezone
            return dt.astimezone(timezone.utc)
        return dt
    
    def _get_julian_day_number(self, dt: datetime) -> int:
        """Get the integer Julian Day Number for caching."""
        astropy_time = Time(dt)
        return int(astropy_time.jd)
    
    def _create_day_grid(self, jd: int) -> Tuple[np.ndarray, np.ndarray]:
        """Create time grid for a day with padding."""
        # Base day starts at JD.5 (noon of previous day)
        base_time = Time(jd, format='jd')
        
        # Create grid from -padding to 24h + padding
        start_offset = -self.padding_minutes / (24 * 60)
        end_offset = 1.0 + self.padding_minutes / (24 * 60)
        
        # Total number of samples including padding
        total_samples = self.samples_per_day + 2 * (self.padding_minutes // self.cache_interval_minutes)
        
        # Create time offsets in days
        time_offsets = np.linspace(start_offset, end_offset, total_samples)
        
        # Create astropy times
        times = base_time + time_offsets
        
        # Convert to JD values for spline x-coordinates (float)
        jd_values = times.jd
        
        return times, jd_values
    
    def _compute_day_cache(self, jd: int) -> Dict:
        """Compute and cache sun positions for a full day with padding."""
        logger.info(f"Computing sun positions for JD {jd}")
        
        astropy_times, jd_values = self._create_day_grid(jd)
        
        # Get sun positions in GCRS frame
        sun = get_sun(astropy_times)
        sun_cart = sun.cartesian
        
        # Extract positions in km (GCRS frame)
        positions_gcrs = np.zeros((len(astropy_times), 3))
        positions_gcrs[:, 0] = sun_cart.x.to('km').value
        positions_gcrs[:, 1] = sun_cart.y.to('km').value
        positions_gcrs[:, 2] = sun_cart.z.to('km').value
        
        # Convert to ITRS frame
        from simple_accgen.propagation.conversions import gcrs_to_itrs
        positions_itrs, _ = gcrs_to_itrs(astropy_times, positions_gcrs, np.zeros_like(positions_gcrs))
        
        # Create a single cubic spline for all 3 coordinates at once
        spline = CubicSpline(jd_values, positions_itrs)
        
        return {
            'spline': spline,
            'jd': jd,
            'created_at': datetime.now(timezone.utc)
        }
    
    def _ensure_cached(self, jd: int):
        """Ensure the given Julian Day is cached."""
        with self._cache_lock:
            if jd in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(jd)
                return
            
            # Compute new cache entry
            cache_entry = self._compute_day_cache(jd)
            
            # Add to cache
            self._cache[jd] = cache_entry
            
            # Remove oldest entries if cache is full
            while len(self._cache) > self.max_cache_days:
                oldest_jd = next(iter(self._cache))
                logger.info(f"Evicting JD {oldest_jd} from cache")
                del self._cache[oldest_jd]
    
    def getStateVectors(self, 
                       times: Union[datetime, List[datetime]], 
                       frame: CoordinateFrame = CoordinateFrame.TEME) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get Sun state vectors for specified time(s) in the requested coordinate frame.
        Uses cached values with cubic spline interpolation.
        """
        # Handle single datetime
        if isinstance(times, datetime):
            times = [times]
        
        if not times:
            return np.array([]), np.array([])
        
        # Validate and convert to UTC
        times = [self._validate_datetime(dt) for dt in times]
        n_times = len(times)
        
        positions = np.zeros((n_times, 3))
        velocities = np.zeros((n_times, 3))
        
        # Group times by Julian Day for efficient caching
        times_by_jd = {}
        for i, dt in enumerate(times):
            jd = self._get_julian_day_number(dt)
            if jd not in times_by_jd:
                times_by_jd[jd] = []
            times_by_jd[jd].append((i, dt))
        
        # Process each day
        for jd, time_list in times_by_jd.items():
            # Ensure this day is cached
            self._ensure_cached(jd)
            
            # Get the cache entry
            with self._cache_lock:
                cache_entry = self._cache[jd]
                spline = cache_entry['spline']
            
            # Interpolate for all times in this day
            indices = [t[0] for t in time_list]
            dts = [t[1] for t in time_list]
            
            # Convert datetimes to Julian Day numbers for interpolation
            jd_floats = np.array([Time(dt).jd for dt in dts])
            
            # Use spline to interpolate all 3 positions at once
            interpolated_positions = spline(jd_floats)
            
            # Assign interpolated positions
            for i, idx in enumerate(indices):
                positions[idx] = interpolated_positions[i]
        
        # We now have positions in ITRS frame
        # Convert to requested frame if necessary
        if frame != CoordinateFrame.ITRS:
            astropy_times = Time(times)
            
            if frame == CoordinateFrame.GCRS:
                from simple_accgen.propagation.conversions import itrs_to_gcrs
                positions, velocities = itrs_to_gcrs(astropy_times, positions, velocities)
            elif frame == CoordinateFrame.TEME:
                # First convert ITRS to GCRS, then GCRS to TEME
                from simple_accgen.propagation.conversions import itrs_to_gcrs, gcrs_to_teme
                positions, velocities = itrs_to_gcrs(astropy_times, positions, velocities)
                positions, velocities = gcrs_to_teme(astropy_times, positions, velocities)
        
        return positions, velocities
    
    def clear_cache(self):
        """Manually clear the entire cache."""
        with self._cache_lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    def cache_info(self) -> Dict:
        """Get information about the current cache state."""
        with self._cache_lock:
            return {
                'cached_days': len(self._cache),
                'max_days': self.max_cache_days,
                'cached_jds': list(self._cache.keys()),
                'cache_interval_minutes': self.cache_interval_minutes,
                'padding_minutes': self.padding_minutes
            }

# For convenience, you can still use the original class name
SunStateVectorProvider = CachedSunStateVectorProvider