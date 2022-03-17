from nodes.core.base import BaseNode

from simpy.core import Environment
import datetime
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


class Propagator(BaseNode):
    def __init__(
        self, env: Environment, name: str, configuration: Dict[str, Any]
    ) -> None:
        super().__init__(env, name, configuration, None)

    def getPosVelAtSimtime(
        self, simtime: Optional[float] = None
    ) -> Tuple[Tuple[Any, Any, Any], Tuple[Any, Any]]:
        return (0.0, 0.0, 0.0), (0.0, 0.0)
