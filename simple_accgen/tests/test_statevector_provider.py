from time import timezone
import pytest
from datetime import datetime, timezone, timedelta
import numpy as np

from simple_accgen.propagation.statevector_provider import CoordinateFrame, GeodeticPoint, TLEStateVectorProvider

class TestStateVectorProvider:

    @pytest.fixture
    def iss_tle(self):
        line1 = "1 25544U 98067A   25096.03700594  .00015269  00000+0  28194-3 0  9999"
        line2 = "2 25544  51.6369 304.3678 0004922  13.5339 346.5781 15.49280872503978"
        return line1, line2
    
    def test_one_time(self, iss_tle):

        t = datetime.fromisoformat("2025-05-04T00:00:00Z").replace(tzinfo=timezone.utc)

        svp = TLEStateVectorProvider(iss_tle[0], iss_tle[1])

        p,v = svp.getStateVectors(t, CoordinateFrame.TEME)

        np.testing.assert_almost_equal(p[0], [5095.29566694,  2006.04948754, -4031.08516514])    
        np.testing.assert_almost_equal(v[0], [-4.84664732,  4.43099726, -3.93031356])


    def test_multiple_times(self, iss_tle):

        t = datetime.fromisoformat("2025-05-04T00:00:00Z").replace(tzinfo=timezone.utc)
        times = [t + timedelta(seconds=dt) for dt in range(0, 86400, 1)]
        
        svp = TLEStateVectorProvider(iss_tle[0], iss_tle[1])

        p,v = svp.getStateVectors(times, CoordinateFrame.TEME)

        np.testing.assert_almost_equal(p[0], [5095.29566694,  2006.04948754, -4031.08516514])    
        np.testing.assert_almost_equal(v[0], [-4.84664732,  4.43099726, -3.93031356])

        np.testing.assert_almost_equal(p[86399], [-4946.1392593, -1856.7302815,  4261.5649175])    
        np.testing.assert_almost_equal(v[86399], [4.8741946, -4.7005472,  3.594125])

    def test_geo_point(self):

        pt = GeodeticPoint.createFromLatLonAlt(0,0,0)
        np.testing.assert_almost_equal(pt.positionITRS, [6378.137,0,0])

        north_pole = GeodeticPoint.createFromLatLonAlt(90,0,0)
        np.testing.assert_almost_equal(north_pole.positionITRS, [0,0,6356.75231425])