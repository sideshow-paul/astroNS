from propagators.base import Propagator

from simpy.core import Environment
from astropy import units as u
from astropy.time import Time

from poliastro.examples import iss

from poliastro.bodies import Earth
from poliastro.twobody import Orbit
from poliastro.core.perturbations import J2_perturbation
from poliastro.twobody.propagation import cowell

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


class Satellite(Propagator):
    def __init__(
        self, env: Environment, name: str, configuration: Dict[str, Any]
    ) -> None:
        super().__init__(env, name, configuration)
        self.format: typeUnion[str, str] = configuration.get("format", "classical")
        self.epoch: typeUnion[str, str] = configuration.get(
            "epoch", "2015-08-26T10:03:00.01Z"
        )
        if self.format == "classical":
            self.sma: typeUnion[str, float] = (
                configuration.get("sma_km", iss.a.to(u.km).value) * u.km
            )
            self.ecc: typeUnion[str, float] = (
                configuration.get("ecc_unitless", iss.ecc.value) * u.one
            )
            self.inc: typeUnion[str, float] = (
                configuration.get("inc_deg", iss.inc.to(u.deg).value) * u.deg
            )
            self.raan: typeUnion[str, float] = (
                configuration.get("raan_deg", iss.raan.to(u.deg).value) * u.deg
            )
            self.ap: typeUnion[str, float] = (
                configuration.get("ap_deg", iss.argp.to(u.deg).value) * u.deg
            )
            self.nu: typeUnion[str, float] = (
                configuration.get("nu_deg", iss.nu.to(u.deg).value) * u.deg
            )

            self.orb = Orbit.from_classical(
                Earth,
                self.sma,
                self.ecc,
                self.inc,
                self.raan,
                self.ap,
                self.nu,
                epoch=Time(self.epoch, format="isot"),
            )
        if self.format == "rv":
            self.rx: typeUnion[str, float] = (
                configuration.get("rx_km", iss.r[0].to(u.km).value) * u.km
            )
            self.ry: typeUnion[str, float] = (
                configuration.get("ry_km", iss.r[1].to(u.km).value) * u.km
            )
            self.rz: typeUnion[str, float] = (
                configuration.get("rz_km", iss.r[2].to(u.km).value) * u.km
            )
            self.vx: typeUnion[str, float] = (
                configuration.get("vx_km", iss.v[0].to(u.km / u.s).value) * u.km / u.s
            )
            self.vy: typeUnion[str, float] = (
                configuration.get("vy_km", iss.v[1].to(u.km / u.s).value) * u.km / u.s
            )
            self.vz: typeUnion[str, float] = (
                configuration.get("vz_km", iss.v[2].to(u.km / u.s).value) * u.km / u.s
            )

            self.orb = Orbit.from_vectors(
                Earth,
                [self.rx, self.ry, self.rz],
                [self.vx, self.vy, self.vz],
                epoch=Time(self.epoch, format="isot"),
            )

    def getCoordsAtSimtime(
        self, simtime: Optional[float] = None
    ) -> Tuple[Tuple[Any, Any, Any], Tuple[Any, Any]]:
        if not simtime:
            simtime = self.env.now

        orb = self.orb.propagate(
            simtime * u.s,
            method=cowell,
            ad=J2_perturbation,
            J2=Earth.J2.value,
            R=Earth.R.to(u.km).value,
        )

        return orb.r.to(u.km), orb.v.to(u.km / u.s)
