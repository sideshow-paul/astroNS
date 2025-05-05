"""The MetaNode is a node that can encompass smaller substructures of nodes.

The metanode may be useful for defining a structure of nodes that may be
co-located or have grouped function.
"""

import json
import datetime
import urllib.request

from nodes.core.base import BaseNode
from propagators import *

from simpy.core import Environment
from typing import (
    cast as typecast,
    List,
    Dict,
    Tuple,
    Any,
    Iterator,
    Optional,
    Callable,
    Type,
    Union as typeUnion,
)


class MetaNode(BaseNode):
    """MetaNode node"""

    def __init__(self, env: Environment, meta_name: str, configuration: Dict[str, Any]):
        """Meta Node initialization from file, json, or restful"""
        super().__init__(env, meta_name, configuration, None)

        # Set properties
        self._source: str = configuration.get("source")
        self._source_type: str = configuration.get("source_type", "file")
        self._signatures: str = configuration.get("signatures", None)
        self._overrides: typeUnion[str, Dict[str, Any]] = configuration.get(
            "overrides", {}
        )

        # Limits scope to only inside a meta node, prevents conflict where
        # networkfactory imports all nodes and this node imports networkfactory

        from interfaces import networkfactory

        # Mandatory field
        if not self._source:
            print(self.log_prefix(), "ERROR: source field not set")
            exit()

        # How is the data formatted?
        if self._source_type == "file":
            print(self.log_prefix() + "loading file: {}".format(self._source))
            network = networkfactory.load_network_file(
                self._source, env, meta_node=self
            )
        elif self.source_type == "json":
            print(self.log_prefix() + "loading json data: {}".format("..."))
            if type(self._source) is str:
                network = networkfactory.load_json_string(
                    self._source, env, meta_node=self
                )
            elif type(self._source) is dict:
                network = networkfactory.load_json_string(
                    json.dumps(self._source), env, meta_node=self
                )
        elif self.source_type == "rest":
            print(self.log_prefix() + "loading REST data from: {}".format(self._source))
            data = urllib.request.urlopen(self._source)
            network = networkfactory.load_json_string(
                data.read().decode(), env, meta_node=self
            )
        else:
            print(
                self.log_prefix()
                + "ERROR: Unsupported source type {}".format(self.network_source)
            )
            exit(1)

        print(self.log_prefix() + "loaded {} nodes".format(len(network)))

        # fix the node names so they don't clash with other meta nodes of the same type
        for node in network:
            node._name = meta_name + "/" + node.name
            node.meta_node = self

        # Store the network
        self.sub_nodes = network

        # Get all possible propagators
        self.propagator_factory = {
            cls.__name__.lower(): cls for cls in Propagator.__subclasses__()
        }
        # import pudb; pu.db
        # Select the class
        if configuration.get("propagator", None) is not None:
            properties = configuration.get("propagator", None)
            prop_fn: Any = self.propagator_factory.get(properties["type"].lower())
            self._propagator = prop_fn(env, meta_name + " propagator", properties)

    @property
    def source(self) -> str:
        """Source of meta configuration"""
        return self._source

    @property
    def source_type(self) -> str:
        """Source type of meta configuration"""
        return self._source_type

    @property
    def propagator(self) -> str:
        """Attach a propagator to a metanode"""
        return self._propagator

    @property
    def signatures(self) -> str:
        """Attach a signature to a metanode -- Not yet implemented"""
        return self._signatures

    @property
    def overrides(self) -> str:
        """Override sub-portions of the metanode -- Not yet implemented"""
        return self._overrides

    def get_location(
        self, simtime: Optional[float]
    ) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float]]]:
        """MetaNode location function, only tries to get position in ECEF geodetic"""
        if self.propagator:
            return self.propagator.getLocationAtSimtime(simtime)
        return None

    def get_coordinates(
        self, simtime: Optional[float]
    ) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float]]]:
        """MetaNode location function, ECI coordinates"""
        if self.propagator:
            return self.propagator.getCoordsAtSimtime(simtime)
        return None

    # needed for base node but shouldn't be called, TODO: Think of a cleaner way
    def execute(self):
        """Executes this function when called, but meta nodes shouldn't be called."""
        delay: float = 0
        processing_time: float = 0
        data_in: Tuple[float, float, List[Tuple]] = None
        data_out_list: List[Tuple] = []
        while True:
            data_in = yield (delay, processing_time, data_out_list)
            data_out_list = [data_in]
