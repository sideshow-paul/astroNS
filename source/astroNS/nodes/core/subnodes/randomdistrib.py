""" Random Distribution node is a special type of node that can fill in a value
for another node by pulling from a distribution as defined by the parameters.

The function returns a response via getValue() function. The response from the
function is what is substituted into the node value.

"""
import random
import bisect
import uuid

from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable

from nodes.core.base import BaseNode


class RandomDistrib(BaseNode):
    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        self.population: List[str] = configuration.get("population", [])
        # [

        #     for item in configuration.get("population", [])
        # ]
        self.weights: List[float] = configuration.get("weights", [])
        # [
        #     float(item) for item in configuration.get("weights", "MISSING").split(",")
        # ]
        self.cdf_vals: List[float] = self.cdf(self.weights)
        self.generates_data_only: bool = True
        super().__init__(env, name, configuration, self.execute())
        self.result_type: Callable

        self.result_key: str = configuration.get("result_key", "size_mbits")
        try:
            pop_type = float(self.population[0])
            self.result_type = float
        except:
            self.result_type = str

        self._time_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_delay", 0.01
        )
        # this will be an on demand node..maybe
        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        return self._time_delay()

    def cdf(self, weights) -> List[float]:
        total: float = sum(weights)
        result: List[float] = []
        cumsum: int = 0
        for w in weights:
            cumsum += w
            result.append(cumsum / total)
        return result

    def execute(self):
        # import pudb; pu.db
        self.generates_data_only: bool = False
        delay: float = 0.0
        processing_time: float = delay
        data_list = []
        #yield 0.0, 0.0, []
        while True:
            data_in = yield (delay, processing_time, data_list)
            x = random.random()
            idx = bisect.bisect(self.cdf_vals, x) - 1
            result = self.result_type(self.population[idx])
            delay = self.time_delay
            processing_time = delay
            id = uuid.uuid4()
            data_in[self.result_key] = result


            data_list = [data_in]
            print(
                self.log_prefix(id)
                + "random value:|{}| set to key:|{}|".format(result, self.result_key)
            )


    def getValue(self):
        x = random.random()
        idx = bisect.bisect(self.cdf_vals, x) - 1
        print(
            self.log_prefix()
            + "getValue() Returned value:|{}|".format(self.population[idx])
        )
        return self.population[idx]
