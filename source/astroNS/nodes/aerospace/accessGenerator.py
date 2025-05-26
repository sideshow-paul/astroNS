

from typing import List, Dict, Tuple, Any, Optional, Callable
from nodes.core.base import BaseNode
import datetime

class AccessGenerator(BaseNode):
    def __init__(self, name: str, inputs: List[str], outputs: List[str]):
        super().__init__(env, name, configuration, self.execute())

        self.env.process(self.run())

    def execute(self, inputs: Dict[str, Any]):
        delay: float = 0.0
        processing_time: float = delay
        data_out_list: List[Tuple] = []
        while True:
            data_in = yield (delay, processing_time, data_out_list)
