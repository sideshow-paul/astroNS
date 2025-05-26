from astropy.coordinates import TEME, ITRS, GCRS, CartesianRepresentation, CartesianDifferential
from astropy import units as u
from astropy.time import Time
import numba
import numpy as np
from datetime import datetime
from typing import List, Tuple, Union
from simple_accgen.constants import WGS84_A, WGS84_F

def datetime_to_jday(times: Union[datetime, List[datetime]]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert datetime object(s) to Julian date components.
    
    Parameters:
    -----------
    times : datetime or List[datetime]
        Single datetime or list of datetimes to convert
        
    Returns:
    --------
    tuple
        (jd, fr) where:
        - jd is a numpy array of Julian dates
        - fr is a numpy array of day fractions
    """
    # Handle single datetime
    if isinstance(times, datetime):
        times = [times]
    
    # Extract time components for vectorized processing
    years = np.array([t.year for t in times], dtype=int)
    months = np.array([t.month for t in times], dtype=int)
    days = np.array([t.day for t in times], dtype=int)
    hours = np.array([t.hour for t in times], dtype=int)
    minutes = np.array([t.minute for t in times], dtype=int)
    seconds = np.array([t.second + t.microsecond/1e6 for t in times], dtype=float)
    
    # Vectorized implementation of jday algorithm
    jd = (367.0 * years
         - 7 * (years + ((months + 9) // 12.0)) * 0.25 // 1.0
         + 275 * months / 9.0 // 1.0
         + days
         + 1721013.5)
    
    # Calculate the fraction of day
    fr = (seconds + minutes * 60.0 + hours * 3600.0) / 86400.0
    
    return jd, fr

def teme_to_itrs(times, positions : np.ndarray, velocities : np.ndarray):
    """
    Convert positions and velocities from TEME to ITRS (ECEF) frame.
    
    Parameters:
    -----------
    times : Time
        Astropy Time array
    positions : ndarray
        Array of positions in TEME frame (shape: n x 3) in km
    velocities : ndarray
        Array of velocities in TEME frame (shape: n x 3) in km/s
        
    Returns:
    --------
    tuple
        (ecef_positions, ecef_velocities) in ITRS/ECEF frame in km and km/s
    """
    # Create CartesianRepresentation and CartesianDifferential for positions and velocities
    teme_pos = CartesianRepresentation(
        positions[:, 0] * u.km,
        positions[:, 1] * u.km,
        positions[:, 2] * u.km
    )
    
    teme_vel = CartesianDifferential(
        velocities[:, 0] * u.km / u.s,
        velocities[:, 1] * u.km / u.s,
        velocities[:, 2] * u.km / u.s
    )
    
    # Combine position and velocity into a single representation
    teme_pos = teme_pos.with_differentials(teme_vel)
    
    # Create TEME coordinate object with velocity information
    teme_coords = TEME(teme_pos, obstime=times)
    
    # Transform to ITRS (ECEF)
    # This transformation properly handles Earth's rotation effects on velocity
    itrs_coords = teme_coords.transform_to(ITRS(obstime=times))
    
    # Extract positions as numpy array in kilometers
    ecef_positions = np.column_stack([
        itrs_coords.x.to(u.km).value,
        itrs_coords.y.to(u.km).value,
        itrs_coords.z.to(u.km).value
    ])
    
    # Extract velocities as numpy array in kilometers per second
    ecef_velocities = np.column_stack([
        itrs_coords.v_x.to(u.km / u.s).value,
        itrs_coords.v_y.to(u.km / u.s).value,
        itrs_coords.v_z.to(u.km / u.s).value
    ])
    
    return ecef_positions, ecef_velocities


def teme_to_gcrs(times, positions, velocities):
    """
    Convert positions and velocities from TEME to icrs (J2000) frame.
    
    Parameters:
    -----------
    times : Time
        Astropy Time array
    positions : ndarray
        Array of positions in TEME frame (shape: n x 3) in km
    velocities : ndarray
        Array of velocities in TEME frame (shape: n x 3) in km/s
        
    Returns:
    --------
    tuple
        (ecef_positions, ecef_velocities) in ITRS/ECEF frame in km and km/s
    """
    # Create CartesianRepresentation and CartesianDifferential for positions and velocities
    teme_pos = CartesianRepresentation(
        positions[:, 0] * u.km,
        positions[:, 1] * u.km,
        positions[:, 2] * u.km
    )

    #     
    teme_vel = CartesianRepresentation(
        velocities[:, 0] * u.km,
        velocities[:, 1] * u.km,
        velocities[:, 2] * u.km
    )
    
    # Create TEME coordinate object with velocity information
    teme_pos_coords = TEME(teme_pos, obstime=times)
    # Create TEME coordinate object with velocity information
    teme_vel_coords = TEME(teme_vel, obstime=times)
    
    # Transform to GCRS (J2000)
    # This transformation properly handles Earth's rotation effects on velocity
    gcrs_pos_coords = teme_pos_coords.transform_to(GCRS(obstime=times))
    gcrs_vel_coords = teme_vel_coords.transform_to(GCRS(obstime=times))
    
    # Extract positions as numpy array in kilometers
    gcrs_positions = np.column_stack([
        gcrs_pos_coords.data.x.to(u.km).value,
        gcrs_pos_coords.data.y.to(u.km).value,
        gcrs_pos_coords.data.z.to(u.km).value
    ])
    
    # Extract velocities as numpy array in kilometers per second
    gcrs_velocities = np.column_stack([
        gcrs_vel_coords.data.x.to(u.km).value,
        gcrs_vel_coords.data.y.to(u.km).value,
        gcrs_vel_coords.data.z.to(u.km).value
    ])
    
    return gcrs_positions, gcrs_velocities

def gcrs_to_itrs(times, positions, velocities):
    """
    Convert positions and velocities from GCRS (J2000) to ITRS (ECEF) frame.
    
    Parameters:
    -----------
    times : Time
        Astropy Time array
    positions : ndarray
        Array of positions in GCRS frame (shape: n x 3) in km
    velocities : ndarray
        Array of velocities in GCRS frame (shape: n x 3) in km/s
        
    Returns:
    --------
    tuple
        (ecef_positions, ecef_velocities) in ITRS/ECEF frame in km and km/s
    """
    # Create CartesianRepresentation for positions
    gcrs_pos = CartesianRepresentation(
        positions[:, 0] * u.km,
        positions[:, 1] * u.km,
        positions[:, 2] * u.km
    )
    
    # Create CartesianDifferential for velocities
    gcrs_vel = CartesianDifferential(
        velocities[:, 0] * u.km / u.s,
        velocities[:, 1] * u.km / u.s,
        velocities[:, 2] * u.km / u.s
    )
    
    # Combine position and velocity into a single representation
    gcrs_pos = gcrs_pos.with_differentials(gcrs_vel)
    
    # Create GCRS coordinate object with velocity information
    gcrs_coords = GCRS(gcrs_pos, obstime=times)
    
    # Transform to ITRS (ECEF)
    itrs_coords = gcrs_coords.transform_to(ITRS(obstime=times))
    
    # Extract positions as numpy array in kilometers
    itrs_positions = np.column_stack([
        itrs_coords.x.to(u.km).value,
        itrs_coords.y.to(u.km).value,
        itrs_coords.z.to(u.km).value
    ])
    
    # Extract velocities as numpy array in kilometers per second
    itrs_velocities = np.column_stack([
        itrs_coords.v_x.to(u.km / u.s).value,
        itrs_coords.v_y.to(u.km / u.s).value,
        itrs_coords.v_z.to(u.km / u.s).value
    ])
    
    return itrs_positions, itrs_velocities


def gcrs_to_teme(times, positions, velocities):
    """
    Convert positions and velocities from GCRS (J2000) to TEME frame.
    
    Parameters:
    -----------
    times : Time
        Astropy Time array
    positions : ndarray
        Array of positions in GCRS frame (shape: n x 3) in km
    velocities : ndarray
        Array of velocities in GCRS frame (shape: n x 3) in km/s
        
    Returns:
    --------
    tuple
        (teme_positions, teme_velocities) in TEME frame in km and km/s
    """
    # Create CartesianRepresentation for positions
    gcrs_pos = CartesianRepresentation(
        positions[:, 0] * u.km,
        positions[:, 1] * u.km,
        positions[:, 2] * u.km
    )
    
    # Create CartesianRepresentation (not Differential) for velocities
    gcrs_vel = CartesianRepresentation(
        velocities[:, 0] * u.km,
        velocities[:, 1] * u.km,
        velocities[:, 2] * u.km
    )
    
    # Create GCRS coordinate objects separately for position and velocity
    gcrs_pos_coords = GCRS(gcrs_pos, obstime=times)
    gcrs_vel_coords = GCRS(gcrs_vel, obstime=times)
    
    # Transform to TEME
    teme_pos_coords = gcrs_pos_coords.transform_to(TEME(obstime=times))
    teme_vel_coords = gcrs_vel_coords.transform_to(TEME(obstime=times))
    
    # Extract positions as numpy array in kilometers
    teme_positions = np.column_stack([
        teme_pos_coords.data.x.to(u.km).value,
        teme_pos_coords.data.y.to(u.km).value,
        teme_pos_coords.data.z.to(u.km).value
    ])
    
    # Extract velocities as numpy array in kilometers
    teme_velocities = np.column_stack([
        teme_vel_coords.data.x.to(u.km).value,
        teme_vel_coords.data.y.to(u.km).value,
        teme_vel_coords.data.z.to(u.km).value
    ])
    
    return teme_positions, teme_velocities


@numba.njit
def geodetic2itrs(lat, lon, alt_km, degrees=False) -> np.ndarray:
    """
    Convert geodetic coordinates to ITRS (ECEF) coordinates.
    
    Parameters:
    -----------
    lat : np.ndarray
        Latitude(s)
    lon : np.ndarray
        Longitude(s)
    alt_km : np.ndarray
        Altitude(s) above WGS84 ellipsoid in km
    degrees: boolean
        if true, then the lat and lon arguments are in degrees
        
    Returns:
    --------
    np.ndarray
        ITRS coordinates with shape (3,) for scalar inputs or (n, 3) for array inputs
    """
    # Using WGS84 ellipsoid parameters
    a = WGS84_A  # semi-major axis in km
    f = WGS84_F  # flattening
    e2 = 2*f - f**2  # eccentricity squared
    
    
    # Get number of points
    n = lat.shape[0]
    
    # Convert degrees to radians if necessary
    lat_rad = np.radians(lat) if degrees else lat
    lon_rad = np.radians(lon) if degrees else lon


    # Initialize output array
    position_itrs = np.zeros((n, 3))
    
    # Calculate each point
    for i in range(n):
        # Calculate N (radius of curvature in the prime vertical)
        N = a / np.sqrt(1 - e2 * np.sin(lat_rad[i])**2)
        
        # Calculate ECEF coordinates (ITRS)
        position_itrs[i, 0] = (N + alt_km[i]) * np.cos(lat_rad[i]) * np.cos(lon_rad[i])
        position_itrs[i, 1] = (N + alt_km[i]) * np.cos(lat_rad[i]) * np.sin(lon_rad[i])
        position_itrs[i, 2] = (N * (1 - e2) + alt_km[i]) * np.sin(lat_rad[i])

    return position_itrs

@numba.njit
def itrs2geodetic(position_itrs: np.ndarray, degrees=False) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convert ITRS (ECEF) coordinates to geodetic coordinates using Ferrari's solution.
    
    Parameters:
    -----------
    position_itrs : np.ndarray
        Array of ITRS coordinates with shape (n, 3) where n is the number of points
        
    Returns:
    --------
    Tuple[np.ndarray, np.ndarray, np.ndarray]
        Arrays of (latitudes in degrees, longitudes in degrees, altitudes in km)
    """
    # WGS84 parameters
    a = WGS84_A  # semi-major axis in km
    f = WGS84_F  # flattening
    b = a * (1 - f)  # semi-minor axis

    e2 = 2*f - f**2  # first eccentricity squared
    ep2 = e2 / (1 - e2)  # second eccentricity squared

    e4 = e2*e2

    a2 = a*a
    b2 = b*b
    
    # Get number of points
    n = position_itrs.shape[0]
    
    # Initialize output arrays
    lat = np.zeros(n)
    lon = np.zeros(n)
    alt = np.zeros(n)
    
    # Process each point
    for i in range(n):
        X = position_itrs[i, 0]
        Y = position_itrs[i, 1]
        Z = position_itrs[i, 2]

        X2 = X*X
        Y2 = Y*Y
        Z2 = Z*Z
        
        # Calculate lon (longitude is easy)
        lon[i] = np.arctan2(Y, X)
        

        # Ferrari's solution for the latitude and altitude
        # Per the solution on Wikipedia https://en.wikipedia.org/wiki/Geographic_coordinate_conversion#The_application_of_Ferrari's_solution
        # Wikipedia as of 5/4/2025 (sometimes things dissapear, but you can see the history)
        #
        # variable names are not super readable, but they match the wiki
        
        p2 = X2+Y2
        p = np.sqrt(p2)
        F = 54*b*b*Z2
        G = p2 + (1-e2)*Z2 - e2*(a2-b2)

        c = (e4*F*p2) / G**3
        c2 = c*c

        s = (1 + c + np.sqrt(c2+2*c)) ** (1.0 / 3.0)
        
        k = s + 1 + 1/s
        k2 = k*k

        P = F / (3*k2*(G**2))

        Q = np.sqrt(1+2*e4*P)

        # r0 is crazy complicated, so we split it up
        r0_0 = (-P*e2*p)/(1+Q)
        r0_1 = (0.5 * a2 * (1+1/Q)) - (P*(1-e2)*Z2) / (Q*(1+Q)) - (0.5 * P * p2)

        r0 = r0_0 + np.sqrt(r0_1)

        U = np.sqrt( (p-e2*r0)**2 + Z2)

        V = np.sqrt( (p-e2*r0)**2 + (1-e2)*Z2)

        z0 = b2*Z / (a*V)

        alt[i] = U * (1-(b2/(a*V)))

        lat[i] = np.arctan( (Z + ep2*z0) / p)

    if degrees:
        lat = np.degrees(lat)
        lon = np.deg2rad(lon)
    
    return lat, lon, alt

def itrs_to_gcrs(times, positions, velocities):
    """
    Convert positions and velocities from ITRS (ECEF) to GCRS (J2000) frame.
    
    Parameters:
    -----------
    times : Time
        Astropy Time array
    positions : ndarray
        Array of positions in ITRS frame (shape: n x 3) in km
    velocities : ndarray
        Array of velocities in ITRS frame (shape: n x 3) in km/s
        
    Returns:
    --------
    tuple
        (gcrs_positions, gcrs_velocities) in GCRS frame in km and km/s
    """
    # Create CartesianRepresentation for positions
    itrs_pos = CartesianRepresentation(
        positions[:, 0] * u.km,
        positions[:, 1] * u.km,
        positions[:, 2] * u.km
    )
    
    # Create CartesianDifferential for velocities
    itrs_vel = CartesianDifferential(
        velocities[:, 0] * u.km / u.s,
        velocities[:, 1] * u.km / u.s,
        velocities[:, 2] * u.km / u.s
    )
    
    # Combine position and velocity into a single representation
    itrs_pos = itrs_pos.with_differentials(itrs_vel)
    
    # Create ITRS coordinate object with velocity information
    itrs_coords = ITRS(itrs_pos, obstime=times)
    
    # Transform to GCRS
    gcrs_coords = itrs_coords.transform_to(GCRS(obstime=times))
    
    # Extract positions using the cartesian property
    cart = gcrs_coords.cartesian
    gcrs_positions = np.column_stack([
        cart.x.to(u.km).value,
        cart.y.to(u.km).value,
        cart.z.to(u.km).value
    ])
    
    # Extract velocities from the differential
    vel = gcrs_coords.cartesian.differentials['s']
    gcrs_velocities = np.column_stack([
        vel.d_x.to(u.km / u.s).value,
        vel.d_y.to(u.km / u.s).value,
        vel.d_z.to(u.km / u.s).value
    ])
    
    return gcrs_positions, gcrs_velocities