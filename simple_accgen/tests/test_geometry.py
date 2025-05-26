import pytest
from datetime import datetime, timedelta, timezone

from simple_accgen.geometry import ObserverTargetGeometry
from simple_accgen.propagation.statevector_provider import GeodeticPoint, TLEStateVectorProvider
import numpy as np
from simple_accgen.propagation.statevector_provider import CoordinateFrame, SunStateVectorProvider
import logging

class TestGeometry:

    @pytest.fixture
    def iss(self):
        line1 = "1 25544U 98067A   25096.03700594  .00015269  00000+0  28194-3 0  9999"
        line2 = "2 25544  51.6369 304.3678 0004922  13.5339 346.5781 15.49280872503978"
        return TLEStateVectorProvider(line1, line2)

    @pytest.fixture
    def target00(self):
        return GeodeticPoint.createFromLatLonAlt(0, 0, 0)

    def test_geometry_90mins(self, iss, target00):


        # Enable logging at INFO level or above
        logging.basicConfig(level=logging.INFO)

        start = datetime.fromisoformat("2025-04-06T00:00:00Z").replace(tzinfo=timezone.utc)
        times = [start + timedelta(hours=dt) for dt in range(0, 200, 1)]

        geom = ObserverTargetGeometry.create(iss, target00, times)
        # print("graze")
        # print(np.degrees(geom.grazing_angle))
        # print("sun")
        # print(np.degrees(geom.sun_elevation_angle))


        # Check cache status
        info = SunStateVectorProvider().cache_info()
        print(info)


def test_sun_caching():
    # Get singleton instance
    sun_provider = SunStateVectorProvider()

    # Clear any existing cache
    sun_provider.clear_cache()
    print("Initial cache info:", sun_provider.cache_info())

    # Test 1: Single time point
    print("\n=== Test 1: Single time point ===")
    time1 = datetime.now(timezone.utc)
    positions1, velocities1 = sun_provider.getStateVectors(time1, frame=CoordinateFrame.ITRS)
    print(f"Position shape: {positions1.shape}")
    print(f"Position: {positions1[0]}")
    print("Cache info after first call:", sun_provider.cache_info())

    # Test 2: Multiple times in the same day
    print("\n=== Test 2: Multiple times same day ===")
    times_same_day = [
        time1,
        time1 + timedelta(hours=1),
        time1 + timedelta(hours=2)
    ]
    positions2, velocities2 = sun_provider.getStateVectors(times_same_day, frame=CoordinateFrame.ITRS)
    print(f"Positions shape: {positions2.shape}")
    print("Cache info (should still be 1 day):", sun_provider.cache_info())

    # Test 3: Times across multiple days
    print("\n=== Test 3: Multiple days ===")
    times_multiple_days = [
        time1,
        time1 + timedelta(days=1),
        time1 + timedelta(days=2)
    ]
    positions3, velocities3 = sun_provider.getStateVectors(times_multiple_days, frame=CoordinateFrame.ITRS)
    print(f"Positions shape: {positions3.shape}")
    print("Cache info (should be 3 days):", sun_provider.cache_info())

    # Test 4: Verify interpolation is working
    print("\n=== Test 4: Interpolation test ===")
    # Get two times 30 seconds apart (between cache points)
    time_a = datetime.now(timezone.utc)
    time_b = time_a + timedelta(seconds=30)

    pos_a, _ = sun_provider.getStateVectors(time_a, frame=CoordinateFrame.ITRS)
    pos_b, _ = sun_provider.getStateVectors(time_b, frame=CoordinateFrame.ITRS)

    # Sun moves slowly, so positions should be very close but not identical
    distance = np.linalg.norm(pos_a - pos_b)
    print(f"Distance between positions 30s apart: {distance:.6f} km")
    print(f"Positions should be close but not identical")

    # Test 5: Different coordinate frames
    print("\n=== Test 5: Different coordinate frames ===")
    pos_itrs, _ = sun_provider.getStateVectors(time1, frame=CoordinateFrame.ITRS)
    pos_gcrs, _ = sun_provider.getStateVectors(time1, frame=CoordinateFrame.GCRS)
    pos_teme, _ = sun_provider.getStateVectors(time1, frame=CoordinateFrame.TEME)

    print(f"ITRS position: {pos_itrs[0]}")
    print(f"GCRS position: {pos_gcrs[0]}")
    print(f"TEME position: {pos_teme[0]}")

    # Test 6: Cache eviction
    print("\n=== Test 6: Cache eviction ===")
    # Fill cache beyond limit
    times_many_days = [time1 + timedelta(days=i) for i in range(10)]
    sun_provider.getStateVectors(times_many_days, frame=CoordinateFrame.ITRS)
    cache_info = sun_provider.cache_info()
    print(f"Cache info after 10 days (should be limited to 7): {cache_info}")
    print(f"Number of cached days: {cache_info['cached_days']}")

    #return sun_provider
