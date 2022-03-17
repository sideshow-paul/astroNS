""" Access takes in a set of time tagged positions in ECI and uses the position
of the current Meta node, along with constraints, to determine if the current
node has access to the target.
"""
import datetime
import numpy as np

from astropy.coordinates import GCRS, ITRS, AltAz
from astropy.time import Time
from astropy import units as u
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable

from nodes.core.base import BaseNode


def hasAccess(source_gcrs, target_gcrs, maxrange):
    """hasAccess determines if the target has access"""
    # Values return in km,km,km
    target_altaz = target_gcrs.transform_to(
        AltAz(
            location=source_gcrs.transform_to(
                ITRS(obstime=source_gcrs.obstime)
            ).earth_location,
            obstime=source_gcrs.obstime,
        )
    )
    if target_altaz.distance.to(u.km) < maxrange * u.km:
        return True
    else:
        # print(target_altaz.distance.to(u.km))
        return False


class Access(BaseNode):
    """Access class"""

    # Two methods by which this node works:
    # 1. Give it a propagator results key with [time1, x1, y1, z1, time2, x2,
    # y2, z2]
    # 2. If the key is set to None, check the node this came from, if this is
    # a different meta node, try to do access to it.
    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize Access node class"""
        super().__init__(env, name, configuration, self.execute())
        ## DEFAULTS
        # Node Reserve Time
        self._processing_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_processing", 0.0
        )
        # Message Delay Time
        self._time_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_delay", 0.0
        )
        ###########
        # Propagator Results
        self._recall_key: Callable[[], Optional[float]] = self.setStringFromConfig(
            "propagator_key", None
        )
        # Access Storage Results
        self._storage_key: Callable[[], Optional[float]] = self.setStringFromConfig(
            "storage_key", "Access_Results"
        )
        # How long access should be checked?
        self._max_duration_s: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "max_duration_s", 0
        )

        self._access_key_name: Callable[[], Optional[str]] = self.setStringFromConfig(
            "add_key", "access"
        )
        self._target_key: Callable[[], Optional[str]] = self.setStringFromConfig(
            "target_key", None
        )
        self._maxRange_km: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "maxRange_km", 3000
        )
        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        return self._time_delay()

    @property
    def recall_key(self) -> Optional[str]:
        return self._recall_key()

    @property
    def storage_key(self) -> Optional[str]:
        return self._storage_key()

    @property
    def target_key(self) -> Optional[str]:
        return self._target_key()

    @property
    def maxRange(self) -> Optional[float]:
        return self._maxRange_km()

    def execute(self):
        """Simpy execution code"""
        delay: float = 0.0
        processing_time: float = delay
        data_out_list: List[Tuple] = []
        while True:
            data_in = yield (delay, processing_time, data_out_list)

            if data_in:
                msg = data_in.copy()
                delay = self.time_delay
                if self.recall_key == "None":
                    # There were no propagated results
                    for i in np.arange(self.env.now, self.env.end_simtime, 60):
                        # print(self._name)
                        source = self.get_coordinates(i)[0]
                        if not self.target_key == "None":
                            target_name = data_in[self.target_key]
                        else:
                            target_name = msg["last_node"]

                        target_node = self.find_node_instance(target_name)
                        target = target_node.get_coordinates(i)[0]

                        epoch_dt = self.env.epoch + datetime.timedelta(
                            seconds=self.env.now + i
                        )
                        epoch_at = Time(
                            epoch_dt.replace(tzinfo=None).isoformat(),
                            format="isot",
                            scale="utc",
                        )
                        source_gcrs = GCRS(
                            x=source[0],
                            y=source[1],
                            z=source[2],
                            obstime=epoch_at,
                            representation_type="cartesian",
                        )
                        target_gcrs = GCRS(
                            x=target[0],
                            y=target[1],
                            z=target[2],
                            representation_type="cartesian",
                        )

                        if hasAccess(source_gcrs, target_gcrs, self._maxRange_km()):
                            break
                    else:
                        # Flag it as a fail
                        i = -1

                    if i != -1:
                        print(
                            self.log_prefix(data_in["ID"])
                            + "Data ID {} arrived at {}. Calculating access to target: {}".format(
                                data_in["ID"],
                                self.env.now,
                                i,
                            )
                        )
                        msg[self.storage_key] = [float(i)]
                    else:
                        print(
                            self.log_prefix(data_in["ID"])
                            + "Data ID {} arrived at {}. No accesses were found.".format(
                                data_in["ID"],
                                self.env.now,
                            )
                        )
                        msg[self.storage_key] = []
                    # There were results
                else:
                    r = msg[self.recall_key]
                    if len(r) % 4 == 0:
                        # There is the correct number of results
                        accesses = []
                        for i in range(0, len(r), 4):
                            t = r[i]
                            x = (r[i + 1] * u.m).to(u.km)
                            y = (r[i + 2] * u.m).to(u.km)
                            z = (r[i + 3] * u.m).to(u.km)

                            epoch_dt = self.env.epoch + datetime.timedelta(
                                seconds=self.env.now + t
                            )
                            epoch_at = Time(
                                epoch_dt.replace(tzinfo=None).isoformat(),
                                format="isot",
                                scale="utc",
                            )
                            source = self.get_coordinates(t)[0]
                            source_gcrs = GCRS(
                                x=source[0],
                                y=source[1],
                                z=source[2],
                                obstime=epoch_at,
                                representation_type="cartesian",
                            )
                            target_gcrs = GCRS(
                                x=x,
                                y=y,
                                z=z,
                                obstime=epoch_at,
                                representation_type="cartesian",
                            )

                            if hasAccess(source_gcrs, target_gcrs, self._maxRange_km()):
                                accesses.append(1)
                            else:
                                accesses.append(0)

                        msg[self.storage_key] = accesses
                    else:
                        print("Invalid Results")

                processing_time = delay
                # Make a copy of the data at this time
                data_out_list = [msg]
            else:
                data_out_list = []
