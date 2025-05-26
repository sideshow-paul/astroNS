import pytest
from simple_accgen.propagation.propagation import generate_satellite_states
from simple_accgen.propagation.conversions import teme_to_gcrs, teme_to_itrs
from datetime import datetime, timedelta, timezone
import numpy as np

class TestPropagation:

    @pytest.fixture
    def iss_tle(self):
        line1 = "1 25544U 98067A   25096.03700594  .00015269  00000+0  28194-3 0  9999"
        line2 = "2 25544  51.6369 304.3678 0004922  13.5339 346.5781 15.49280872503978"
        return line1, line2

    def test_propagate_iss(self, iss_tle):

        start = datetime.fromisoformat("2025-04-06T00:00:00Z").replace(tzinfo=timezone.utc)
        times = [start + timedelta(seconds=dt) for dt in range(0, 86401, 60)]

        t, r, v = generate_satellite_states(iss_tle[0], iss_tle[1], times)

        assert np.shape(t) == (1441,)
        assert np.shape(r) == (1441,3)
        assert np.shape(v) == (1441,3)

        np.testing.assert_almost_equal(r[0], np.array( [-1915.75042525,  6079.44030157,  2360.84000426]))
        np.testing.assert_almost_equal(v[0], np.array( [-5.436351 ,  0.3883057, -5.3823035]))

        r_ecef, v_ecef = teme_to_itrs(t,r,v)
        np.testing.assert_almost_equal(r_ecef[0], np.array( [328.5351714, -6365.6747649,  2360.8280383]))
        np.testing.assert_almost_equal(v_ecef[0], np.array( [4.70067353, -1.76430368, -5.38230816]))

        r_j2000, v_j2000 = teme_to_gcrs(t,r,v)
        np.testing.assert_almost_equal(r_j2000[0], np.array( [-1875.57278878,  6090.25790241,  2365.21563372]))
        np.testing.assert_almost_equal(v_j2000[0], np.array( [-5.44727356,  0.4187999,  -5.36895727]))





