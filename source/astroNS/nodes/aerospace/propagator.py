""" Propagator node creates a list of time-tagged values for the future 
positions of the meta node of which it is contained.

The Propagator node will store the results to a key to pass in future messages
and will also create a visualization via CZML if set to a non-default time.
"""
import os
import datetime
import uuid
import random

rd = random.Random()
rd.seed(1)
uuid.uuid4 = lambda: uuid.UUID(int=rd.getrandbits(128))

import numpy as np
import astropy.units as u

from czml3 import Document, Packet, Preamble
from czml3.enums import (
    HorizontalOrigins,
    InterpolationAlgorithms,
    LabelStyles,
    ReferenceFrames,
    VerticalOrigins,
)
from czml3.properties import (
    Billboard,
    Clock,
    Color,
    Label,
    Material,
    Path,
    Position,
    SolidColorMaterial,
)
from czml3.types import IntervalValue, Sequence, TimeInterval
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable

from nodes.core.base import BaseNode


class Propagator(BaseNode):
    """Propagator class"""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize Propagator node class"""
        super().__init__(env, name, configuration, self.execute())
        self._processing_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_processing", 0.0
        )
        self._time_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_delay", 0.0
        )
        self._storage_key: Callable[[], Optional[float]] = self.setStringFromConfig(
            "storage_key", "Propagator_Results"
        )
        self._max_duration_s: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "max_duration_s", 0
        )
        self._time_step_s: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_step_s", 60
        )
        self._max_viz_time_s: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "max_viz_time_s", 0
        )
        self.env.process(self.run())

    @property
    def time_processing(self) -> Optional[float]:
        """
        Sample
        ::
            Propagator:
                type: Propagator
                time_processing: 10

        Default value: 0

        In this case, the Propagator node does nothing except delay the message.
        However, the node is incapable of processing other messages during this
        time.
        """
        return self._time_processing() * u.s

    @property
    def time_delay(self) -> Optional[float]:
        """
        Sample
        ::
            Propagator:
                type: Propagator
                time_delay: 10

        Default value: 0

        In this case the Propagator node does nothing except delay the message.
        This should be done with :func:`~astroNS.nodes.network.delaytime`, but
        it can be combined with the other properties.
        """
        return self._time_delay() * u.s

    @property
    def storage_key(self) -> Optional[str]:
        """
        Sample
        ::
            Propagator:
                type: Propagator
                time_processing: 25
                storage_key: Propagator_Results
                max_duration_s: 60

        Default value: Propagator_Results

        This will generate 60 seconds of propagation and store the results to
        the message key "Propagator_Results". It will also reserve the node
        from doing any other work for 25 seconds. This might represent an Orbit
        Analyst creating an ephemeris file.

        The propagation will always start from the time the message is received.
        Additionally, the default max_duration_s is 0, so it is set here.
        """
        return self._storage_key()

    @property
    def max_duration(self) -> Optional[float]:
        """
        Sample
        ::
            Propagator:
                type: Propagator
                time_delay: 10
                max_duration_s: 120

        Default value: 0

        This will generate 120 seconds of propagation and store the results to
        the default message key "Propagator_Results". It will also delay the
        message by 10 seconds, while the node is ready to do other work.
        """
        return self._max_duration_s() * u.s

    @property
    def time_step(self) -> Optional[float]:
        """
        Sample
        ::
            Propagator:
                type: Propagator
                max_duration_s: 60
                time_step_s: 1

        Default value: 60

        This will generate 60 seconds of propagation and store the results to
        the message key "Propagator_Results" with intervals of 1 second. The
        outgoing message has no delay.
        """
        return self._time_step_s() * u.s

    @property
    def max_viz_time(self) -> Optional[float]:
        """
        Sample
        ::
            Propagator:
                type: Propagator
                max_duration_s: 86400
                time_step_s: 60
                max_viz_time_s: 3600

        Default value: 0

        This will generate one day of propagation and store the results to
        the message key "Propagator_Results" with intervals of 60 seconds. The
        outgoing message has no delay. However, it will create a CZML file that
        covers the first hour.

        """
        return self._max_viz_time_s() * u.s

    def execute(self):
        """Simpy execution code"""
        reserve_time: float = 0.0
        total_delay: float = reserve_time
        data_out_list: List[Tuple] = []
        while True:
            data_in = yield (reserve_time, total_delay, data_out_list)

            if data_in:
                total_delay = reserve_time + self.time_delay.to(u.s).value
                msg = data_in.copy()

                if self.max_duration > 0 * u.s:
                    # Float Time
                    f_start = self.env.now
                    f_stop = min(
                        self.env.end_simtime,
                        self.env.now + self.max_viz_time.to(u.s).value,
                    )

                    data = []
                    for i in np.arange(f_start, f_stop, self.time_step.to(u.s).value):
                        source = self.get_coordinates(i)[0]
                        data.append(i)
                        data.append(source[0].to(u.m).value)
                        data.append(source[1].to(u.m).value)
                        data.append(source[2].to(u.m).value)

                    msg[self.storage_key] = data
                    data_out_list = [msg]

                    start = self.env.epoch
                    end = self.env.epoch + datetime.timedelta(
                        seconds=self.env.end_simtime
                    )

                    # ISO Time
                    i_start = self.env.epoch + datetime.timedelta(seconds=f_start)
                    i_stop = self.env.epoch + datetime.timedelta(seconds=f_stop)

                    simple = Document(
                        [
                            Preamble(
                                name="simple",
                                clock=IntervalValue(
                                    start=start,
                                    end=end,
                                    value=Clock(currentTime=i_start, multiplier=60),
                                ),
                            ),
                            Packet(
                                id=str(uuid.uuid4()),
                                name=self.get_parent().name,
                                availability=TimeInterval(start=i_start, end=i_stop),
                                billboard=Billboard(
                                    horizontalOrigin=HorizontalOrigins.CENTER,
                                    image=(
                                        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9"
                                        "hAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdv"
                                        "qGQAAADJSURBVDhPnZHRDcMgEEMZjVEYpaNklIzSEfLfD4qNnXAJSFWfhO7w2Zc0T"
                                        "f9QG2rXrEzSUeZLOGm47WoH95x3Hl3jEgilvDgsOQUTqsNl68ezEwn1vae6lceSEE"
                                        "YvvWNT/Rxc4CXQNGadho1NXoJ+9iaqc2xi2xbt23PJCDIB6TQjOC6Bho/sDy3fBQT"
                                        "8PrVhibU7yBFcEPaRxOoeTwbwByCOYf9VGp1BYI1BA+EeHhmfzKbBoJEQwn1yzUZt"
                                        "yspIQUha85MpkNIXB7GizqDEECsAAAAASUVORK5CYII="
                                    ),
                                    scale=1.5,
                                    show=True,
                                    verticalOrigin=VerticalOrigins.CENTER,
                                ),
                                label=Label(
                                    horizontalOrigin=HorizontalOrigins.LEFT,
                                    outlineWidth=2,
                                    show=True,
                                    font="11pt Lucida Console",
                                    style=LabelStyles.FILL_AND_OUTLINE,
                                    text=self.get_parent().name,
                                    verticalOrigin=VerticalOrigins.CENTER,
                                    fillColor=Color.from_list([0, 255, 0]),
                                    outlineColor=Color.from_list([0, 0, 0]),
                                ),
                                path=Path(
                                    show=Sequence(
                                        [
                                            IntervalValue(
                                                start=i_start, end=i_stop, value=True
                                            )
                                        ]
                                    ),
                                    width=1,
                                    resolution=120,
                                    material=Material(
                                        solidColor=SolidColorMaterial.from_list(
                                            [0, 255, 0]
                                        )
                                    ),
                                ),
                                position=Position(
                                    interpolationAlgorithm=InterpolationAlgorithms.LAGRANGE,
                                    interpolationDegree=5,
                                    referenceFrame=ReferenceFrames.INERTIAL,
                                    epoch=start,
                                    cartesian=data,
                                ),
                            ),
                        ]
                    )

                    filename = "{}/czml/{}/{}.czml".format(
                        self.env.path_to_results, self.name, str(self.env.now)
                    )

                    os.makedirs(os.path.dirname(filename), exist_ok=True)
                    with open(filename, "w") as f:
                        f.write(simple.dumps())
                    f.close()
                else:
                    # No visualization will be output
                    pass
            else:
                data_out_list = []
