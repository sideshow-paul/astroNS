import numpy as np
from datetime import timedelta
import sgp4
from sgp4.api import jday
import sgp4.api
from sgp4.model import Satellite, Satrec
from sgp4.earth_gravity import wgs84
from astropy.time import Time
from typing import Union, List
from datetime import datetime
from simple_accgen.propagation.conversions import datetime_to_jday

def generate_satellite_states(tle_line1, tle_line2, times: Union[datetime, List[datetime]]):
    """
    Generate satellite state vectors for a specified time range at regular intervals.
    
    Parameters:
    -----------
    tle_line1 : str
        First line of the TLE
    tle_line2 : str
        Second line of the TLE
    start_time : datetime
        Start time for propagation
    end_time : datetime
        End time for propagation
    step_seconds : int, optional
        Time step in seconds, default is 1 second
        
    Returns:
    --------
    tuple
        (times, positions, velocities) where:
        - times is an array of astropy Time objects
        - positions is a numpy array of shape (n, 3) in km in TEME frame
        - velocities is a numpy array of shape (n, 3) in km/s in TEME frame
    """
    # Create satellite object from TLE
    satellite = Satrec.twoline2rv(tle_line1, tle_line2, 2) # 2 == WGS84
    print()
    print("***************************************************")
    print(satellite)
    print(sgp4.api.accelerated)
    print("===================================================")
    
    # Handle single datetime
    if isinstance(times, datetime):
        times = [times]
    
    jd, fr = datetime_to_jday(times)
    
    # Use the vectorized sgp4_array method for efficiency
    e, r, v = satellite.sgp4_array(jd, fr)
    
    # Check for errors
    if np.any(e != 0):
        error_indices = np.where(e != 0)[0]
        print(f"SGP4 errors at indices: {error_indices}")
        # Set error positions and velocities to NaN
        r[error_indices] = np.nan
        v[error_indices] = np.nan
    
    # Convert times to Astropy Time objects for later coordinate transformations
    astropy_times = Time(times)
    
    return astropy_times, r, v