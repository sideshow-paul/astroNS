import datetime

from propagators.base import Propagator

from astropy.coordinates import EarthLocation, GCRS
from astropy.time import Time
from astropy import units as u

from simpy.core import Environment
from typing import (
    List,
    Dict,
    Tuple,
    Any,
    Iterator,
    Optional,
    Type,
    Callable,
    Generator,
    Iterable,
    Union as typeUnion,
)


class GeoPoint(Propagator):
    def __init__(
        self, env: Environment, name: str, configuration: Dict[str, Any]
    ) -> None:
        super().__init__(env, name, configuration)
        self.lat: typeUnion[str, float] = configuration.get("Lat_deg", 0.0)
        self.lon: typeUnion[str, float] = configuration.get("Lon_deg", 0.0)
        self.alt: typeUnion[str, float] = configuration.get("Alt_km", 0.0)

        self.angle_off_north: typeUnion[str, float] = configuration.get(
            "angle_off_north_deg", 0.0
        )
        self.velocity: float = 0.0

        self._el = EarthLocation.from_geodetic(
            self.lon * u.deg, self.lat * u.deg, self.alt * u.km
        )

    def getLocationAtSimtime(
        self, simtime: Optional[float] = None
    ) -> Tuple[Tuple[Any, Any, Any], Tuple[Any, Any]]:
        if not simtime:
            simtime = self.env.now
        #!TODO Incorporate velocity
        return (
            self._el.lat.to(u.deg).value,
            self._el.lon.to(u.deg).value,
            self._el.height.to(u.km).value,
        ), (0, 0, 0)

    def getCoordsAtSimtime(
        self, simtime: Optional[float] = None
    ) -> Tuple[Tuple[Any, Any, Any], Tuple[Any, Any]]:
        if not simtime:
            simtime = self.env.now
        #!TODO Incorporate velocity
        epoch_time = (self.env.epoch + datetime.timedelta(seconds=simtime)).replace(
            tzinfo=None
        )
        time_epoch_time = Time(epoch_time.isoformat(), format="isot", scale="utc")
        itrs = self._el.get_itrs(obstime=time_epoch_time)
        gcrs = itrs.transform_to(GCRS(obstime=time_epoch_time))
        return (
            gcrs.cartesian.x.to(u.km),
            gcrs.cartesian.y.to(u.km),
            gcrs.cartesian.z.to(u.km),
        ), (0, 0, 0)
