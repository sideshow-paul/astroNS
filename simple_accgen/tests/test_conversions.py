from datetime import datetime
import numpy as np

from simple_accgen.propagation.conversions import (
    datetime_to_jday,
    geodetic2itrs,
    itrs2geodetic,
)


def test_datetime_to_jday():
    """Test the datetime_to_jday function."""

    # Test case 1: Single datetime
    test_time = datetime(2020, 2, 11, 13, 57, 0)
    jd, fr = datetime_to_jday(test_time)

    # Expected values based on the example in the original jday docstring
    expected_jd = [2458890.5]
    expected_fr = [0.58125]

    assert isinstance(jd, np.ndarray)
    assert isinstance(fr, np.ndarray)
    assert jd.shape == (1,)
    assert fr.shape == (1,)

    assert np.isclose(jd[0], expected_jd)
    assert np.isclose(fr[0], expected_fr)

    # Test case 2: List of datetimes
    test_times = [
        datetime(2020, 2, 11, 13, 57, 0),  # Same as above
        datetime(2020, 2, 11, 0, 0, 0),  # Midnight
        datetime(2000, 1, 1, 12, 0, 0),  # Y2K noon
        datetime(2025, 12, 31, 23, 59, 59, 0),  # Almost 2026
    ]

    jd, fr = datetime_to_jday(test_times)

    # Expected values
    expected_jds = np.array(
        [
            2458890.5,  # 2020-02-11
            2458890.5,  # 2020-02-11 (same day)
            2451545.0,  # 2000-01-01
            2461040.5,  # 2025-12-31
        ]
    )

    # [2458890.5 2458890.5 2451544.5 2461040.5]

    expected_frs = np.array(
        [
            0.58125,  # 13:57:00
            0.0,  # 00:00:00
            0.5,  # 12:00:00
            0.99998843,  # 23:59:59.999999
        ]
    )

    assert jd.shape == (4,)
    assert fr.shape == (4,)
    assert np.allclose(jd, expected_jds)
    assert np.allclose(fr, expected_frs)

    # Test case 3: Edge case - leap year
    leap_year_time = datetime(2024, 2, 29, 15, 30, 0)
    jd, fr = datetime_to_jday(leap_year_time)

    # Expected value verified against astronomical references
    assert np.isclose(jd[0], 2460370.5)
    assert np.isclose(fr[0], 0.6458333333333334)

    # Test case 4: Edge case - very large times
    future_time = datetime(3000, 1, 1, 0, 0, 0)
    jd, fr = datetime_to_jday(future_time)

    # Expected value
    assert np.isclose(jd[0], 2816787.5)
    assert np.isclose(fr[0], 0.0)


def test_lla2ecf():

    np.testing.assert_almost_equal(
        geodetic2itrs(np.array([0.0]),
                      np.array([0.0]),
                      np.array([0.0])),
        [[
            6378.137,
            0.0,
            0.0,
        ]],
    )

    np.testing.assert_almost_equal(
    geodetic2itrs(np.array([90.0]),
                    np.array([0.0]),
                    np.array([0.0]), degrees=True),
    [[
        0.0,
        0.0,
        6356.7523142,
    ]])




def test_lla2ecef_and_back():
    """
    Test the conversion from geodetic (LLA) to ECEF and back.

    This function:
    1. Generates 10 random points with latitudes (-90 to 90), longitudes (-180 to 180),
       and altitudes (0 to 50 km)
    2. Converts these points to ECEF coordinates
    3. Converts back to geodetic coordinates
    4. Compares the original and reconstructed coordinates
    """
    import numpy as np
    import random

    # Set random seed for reproducibility
    np.random.seed(42)

    # Number of test points
    n = 10000

    # Generate random geodetic coordinates
    lat_deg = np.random.uniform(-90, 90, n)
    lon_deg = np.random.uniform(-180, 180, n)
    alt_km = np.random.uniform(0, 50, n)  # Altitudes from 0 to 50 km

    # Convert to ECEF
    ecef_coords = geodetic2itrs(lat_deg, lon_deg, alt_km)

    # Convert back to geodetic
    lat_deg_back, lon_deg_back, alt_km_back = itrs2geodetic(ecef_coords)

    # Calculate differences
    lat_diff = np.abs(lat_deg - lat_deg_back)
    lon_diff = np.abs(lon_deg - lon_deg_back)
    # Handle longitude wrap-around at 180 degrees
    lon_diff = np.minimum(lon_diff, 360 - lon_diff)
    alt_diff = np.abs(alt_km - alt_km_back)

    # Calculate and print statistics
    max_lat_diff = np.max(lat_diff)
    max_lon_diff = np.max(lon_diff)
    max_alt_diff = np.max(alt_diff)

    mean_lat_diff = np.mean(lat_diff)
    mean_lon_diff = np.mean(lon_diff)
    mean_alt_diff = np.mean(alt_diff)

    print("\nStatistics:")
    print(f"Maximum differences: Lat: {max_lat_diff:.10f}°, Lon: {max_lon_diff:.10f}°, Alt: {max_alt_diff:.10f} km")
    print(f"Mean differences: Lat: {mean_lat_diff:.10f}°, Lon: {mean_lon_diff:.10f}°, Alt: {mean_alt_diff:.10f} km")

    # Overall success criteria
    success = (max_lat_diff < 1e-8 and max_lon_diff < 1e-8 and max_alt_diff < 1e-8)
    print(f"\nTest {'PASSED' if success else 'FAILED'}")

    #return success
