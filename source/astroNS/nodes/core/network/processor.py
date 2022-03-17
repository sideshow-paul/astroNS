"""
Processor is a node that calculates how long it takes to process a message.
"""

import pandas as pd
import uuid
from heapq import heappush, heappop
from numpy import random
from simpy.core import Environment

from nodes.core.base import BaseNode

from typing import Dict, List, Tuple, Any, Callable, Optional, Union as typeUnion


class Processor(BaseNode):
    """Processor is a node that takes in message size, processing rate, and number of processors and outputs the time
    it takes to process the messages."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initializes the node"""
        self.cpuStackMode: typeUnion[str, bool] = configuration.get(
            "cpuStackMode", False
        )
        self.returnToSender: typeUnion[str, bool] = configuration.get(
            "returnToSender", False
        )
        self.transformFn: typeUnion[str, bool] = configuration.get(
            "transform_fn", lambda d: d
        )
        self.num_cpus: int = int(configuration.get("num_of_cpus", 1))
        self.cpus: List[Tuple[int, float]] = []

        if self.cpuStackMode:
            for cpu in range(self.num_cpus):
                self.cpus.append((cpu, 0.0))
        else:
            for cpu in range(self.num_cpus):
                heappush(self.cpus, (0.0, (cpu)))  # type: ignore
        super().__init__(env, name, configuration, self.execute())
        self._rate_per_mbit: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "rate_per_mbit", 100.0
        )
        self.cpu_time_idle: List[float] = []
        self.cpu_processing_time: List[float] = []
        self.cpu_used: List[float] = []
        self.env.process(self.run())

    @property
    def rate_per_mbit(self) -> Optional[float]:
        """Processing rate per Mbit"""
        return self._rate_per_mbit()

    # override the stats call to add cpu_idle to it
    def create_history_dataframe(self):
        """Override the stats call to add cpu_idle to it"""
        df = super().create_history_dataframe()
        df["cpu_idle"] = pd.Series(self.cpu_time_idle, index=df.index)
        df["processing_time"] = pd.Series(self.cpu_processing_time, index=df.index)
        df["cpu_used"] = pd.Series(self.cpu_used, index=df.index)
        return df

    # called from base node via next() call
    def execute(self):
        """Execute function for the processor node"""
        delay: float = 0
        processing_time: float = 0
        new_data = None
        new_data_list: List[Dict[str, Any]] = []

        while True:
            data_in = yield (delay, processing_time, new_data_list)
            print(self.log_prefix(data_in["ID"]) + "CPUs state: |{}|".format(self.cpus))

            if self.cpuStackMode:
                cpu_to_use, simtime_available = next(
                    (cpu_time for cpu_time in self.cpus if cpu_time[1] < self.env.now),
                    min(self.cpus, key=lambda cpu_time: cpu_time[1]),
                )
                self.cpus.remove((cpu_to_use, simtime_available))
            else:
                simtime_available, cpu_to_use = heappop(self.cpus)

            time_waiting: float = max(0.0, simtime_available - data_in["time_sent"])
            time_idle: float = max(0.0, self.env.now - simtime_available)
            self.cpu_time_idle.append(time_idle)
            processing_time: float = data_in[self.msg_size_key] / self.rate_per_mbit
            self.cpu_processing_time.append(processing_time)
            self.cpu_used.append(cpu_to_use)

            if self.cpuStackMode:
                self.cpus.insert(
                    cpu_to_use, (cpu_to_use, self.env.now + processing_time)
                )
                cpu_peek, next_cpu_available_peek = min(
                    self.cpus, key=lambda cpu_time: cpu_time[1]
                )
            else:
                heappush(self.cpus, (self.env.now + processing_time, cpu_to_use))
                next_cpu_available_peek, cpu_peek = self.cpus[0]

            delay: float = max(0.0, next_cpu_available_peek - self.env.now)
            # data_out: Dict[str, Any] = {
            #     "ID": uuid.uuid4(),
            #     self.msg_size_key: random.randint(10, 200),
            # }
            data_out = data_in
            # data_in  key/values does not overwrite new key/values in data_out
            data_out: Dict[Tuple[float, float, List[Tuple]], Dict[str, Any]] = {
                **data_in,
                **data_out,
            }

            # data_out = data_in
            # if data_in has a to and from, then switch them
            if self.returnToSender:
                if "from" in data_in.keys():
                    data_out["to"] = data_in["from"]
                if "to" in data_in.keys():
                    data_out["from"] = data_in["to"]
                print(
                    self.log_prefix(data_in["ID"])
                    + "Setting 'to' field to |{}|, setting 'from' to |{}|".format(
                        data_out["to"], data_out["from"]
                    )
                )

            new_data_list = [data_out]

            print(
                self.log_prefix(data_in["ID"])
                + "Data size of |%d| arrived at |%d|. CPU used: |%d| Processing Time: |%f|, wait for CPU: |%f| Total:|%f| CPU idle: |%f|"
                % (
                    data_in[self.msg_size_key],
                    self.env.now,
                    cpu_to_use,
                    processing_time,
                    time_waiting,
                    time_waiting + processing_time,
                    time_idle,
                )
            )
            # processing_time += time_waiting
