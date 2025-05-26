from tarfile import REGULAR_TYPES
import pytest
from datetime import datetime, timedelta, timezone

from simple_accgen.access_generator import AccessGenerator, GrazingAngleFilter, TargetSunElevationAngleFilter
from simple_accgen.geometry import ObserverTargetGeometry
from simple_accgen.propagation.statevector_provider import GeodeticPoint, TLEStateVectorProvider
import numpy as np

class TestGeometry:

    @pytest.fixture
    def iss(self):
        line1 = "1 25544U 98067A   25124.47945869  .00007832  00000-0  14843-3 0  9999"
        line2 = "2 25544  51.6347 163.5573 0002292  78.0470 282.0775 15.49336034508382"
        return TLEStateVectorProvider(line1, line2)
    
    @pytest.fixture
    def targetAshburn(self):
        return GeodeticPoint.createFromLatLonAlt(39.0438, -77.4874, 0)
    
    def test_accgen_1day(self, iss, targetAshburn):
        
        start = datetime.fromisoformat("2025-05-05T00:00:00Z").replace(tzinfo=timezone.utc)
        times = [start + timedelta(seconds=dt) for dt in range(0, 86400*3, 1)]
    
        geom = ObserverTargetGeometry.create(iss, targetAshburn, times)

        access_gen = AccessGenerator(geom)
        access_gen.add_filter( GrazingAngleFilter(min_angle=10, degrees=True))
        access_gen.add_filter( TargetSunElevationAngleFilter(min_angle=-90, max_angle=0, degrees=True))

        # Get the access regions
        regions = access_gen.generate_access_regions()
        

        # Get the timestamps for each region
        access_times = access_gen.get_access_timestamps(regions)
        for i, (start_time, end_time) in enumerate(access_times):
            print(f"Access {i+1}: {start_time} to {end_time}")


        # Verify that all grazing angles in each region meet the constraint
        for start_idx, end_idx in regions:
            region_grazes = np.degrees(geom.grazing_angle[start_idx:end_idx+1])  # +1 because end_idx is inclusive
            assert np.all(region_grazes >= 0), f"Found grazing angles < 0 in region {start_idx}:{end_idx}"
            
            # Optional: Print some statistics about this region
            print(f"Graze {start_idx}:{end_idx} - Min: {np.min(region_grazes)}, Max: {np.max(region_grazes)}")

            region_suns = np.degrees(geom.sun_elevation_angle[start_idx:end_idx+1])
            assert np.all(region_suns <= 0), f"Found sun angles > 0 in region {start_idx}:{end_idx}"

            # Optional: Print some statistics about this region
            print(f"Sun {start_idx}:{end_idx} - Min: {np.min(region_suns)}, Max: {np.max(region_suns)}")

    