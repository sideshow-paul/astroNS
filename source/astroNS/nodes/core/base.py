""" The Base Node is the base structure of which all nodes are constructed.

The base node is not a functional node and should not be used. It does however
give all nodes the similar functionality and only needs to be defined in areas
where the node functions differently from the base node.

"""
from __future__ import absolute_import, unicode_literals  # , annotations

import simpy
import pandas as pd
import random

import re
import csv
import bisect
import ast
import datetime

import platform

from links import *

from simpy.util import start_delayed

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

# Define Type hints
Event = Dict[str, Any]


def addToMap(key, node_name, inout):
    """Maps link usage for this node, including all in links and out links.

    This function was moved from :func:`make_link_map_data`.

    :param key: The name of the link
    :param node_name: The name of the node_name
    :param inout: String that tells whether this is an "in" link or "out" link
    :return: None
    """
    if not key in BaseNode.mapping:
        BaseNode.mapping[key] = {"in": [], "out": [], "wait": 0.0}
    BaseNode.mapping[key][inout].append(node_name)


class BaseNode:
    """
    This class is shared among all the nodes.
    """

    msg_history: Dict[
        str, List[Tuple[float, datetime.date, "BaseNode", str, List[str], float]]
    ] = {}
    stop_signal = 999999.42

    nodes: Dict[str, "BaseNode"] = {}
    node_list: List["BaseNode"] = []
    mapping: Dict[str, Dict[str, Any]] = {}
    out_labels: Dict[str, str] = {}
    node_names: List[str] = []

    # for network animation
    old_simtime = 0
    log_time_group: List[str] = []
    current_frame_number = 0

    def find_node_instance(self, node_name: str) -> Optional["BaseNode"]:
        """
        Finds a node given a name
        :param node_name: a str, the name of the node to find
        :return: A BaseNode, or None

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> b = BaseNode(env, 'test_name', {}, None)
        >>> b.find_node_instance('test_name').name
        'test_name'
        >>> b.find_node_instance('not_here')

        """
        # for node_instance in self.node_list:
        #    print(node_instance.name)

        return next(
            (
                node_instance
                for node_instance in self.node_list
                if node_instance.name.lower() == node_name.lower()
            ),
            None,
        )

    def get_parent(self):
        name = self._name  # FORGE/Outbound, KSAT/Hawaii/Outbound
        parent = name[: name.rfind("/")]  # Outbound, KSAT/Hawaii
        if "/" in parent:
            parent = parent[parent.find("/") + 1 :]
        return self.find_node_instance(parent)

    def get_location(
        self, simtime: float
    ) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float]]]:
        """
        Returns a location tuple of self.meta_node, or None
        :param simtime: a float with the current time
        :return: ((latitude, longitude, altitude), (velocity, unknown))
        """

        return self.get_parent().get_location(simtime) if self.meta_node else None
        # return None

    def get_coordinates(
        self, simtime: float
    ) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float]]]:
        """
        Returns a location tuple of self.meta_node, or None
        :param simtime: a float with the current time
        :return: ((latitude, longitude, altitude), (velocity, unknown))
        """
        if self.meta_node is None:
            print("{} -- This node does not belong to a meta node.".format(self._name))
        else:
            if self.get_parent()._propagator is None:
                print(
                    "{} -- This node does not have a propagator.".format(
                        self.get_parent()
                    )
                )

        return self.get_parent().get_coordinates(simtime) if self.meta_node else None
        # return None

    @staticmethod
    def make_link_map_data(nodes: List["BaseNode"]) -> None:
        """
        Static function so lack of self is intended.
        Sets static variable BaseNode.mapping to a dict with links between nodes
        :param nodes: a list of nodes
        :return: None

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> from source.python_lib.NodePipe import NodePipe
        >>> b = BaseNode(env, 'node_b', {}, None)
        >>> c = BaseNode(env, 'node_c', {}, None)
        >>> b.in_pipe = NodePipe(env)
        >>> b.in_pipe.pipes.append(b.in_pipe)
        >>> c.out_pipe_conns = b.in_pipe
        >>> BaseNode.make_link_map_data([b, c])
        >>> BaseNode.mapping
        {'<NodePipe: pipes: [<NodePipe: pipes: [...]>]>': {'in': ['node_b'], 'out': ['node_c'], 'wait': 0.0}}

        """

        for node in nodes:
            BaseNode.node_names.append(node.name)

            if node.in_pipe:
                addToMap(str(node.in_pipe), node.name, "in")

            if node.out_pipe_conns:
                for out_pipe in node.out_pipe_conns.pipes:
                    addToMap(str(out_pipe), node.name, "out")
                    BaseNode.out_labels[str(out_pipe)] = ""

                for predicate, store in node.out_pipe_conns.predicates_to_pipe:
                    addToMap(str(store), node.name, "out")
                    BaseNode.out_labels[
                        str(store)
                    ] = node.out_pipe_conns.predicates_to_string[predicate]

    @property
    def name(self) -> str:
        """
        name getter
        :return: str name

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> b = BaseNode(env, 'test_name', {}, None)
        >>> b.name
        'test_name'

        """
        return self._name

    def __init__(
        self,
        env: simpy.Environment,
        name: str,
        configuration: Dict[str, Any],
        node_generator: Optional[
            Generator[Tuple[float, float, List[Event]], Event, None]
        ],
    ):
        """
        Constructor. makes a new BaseNode
        may have to condense these
        :param env: a simpy Environment
        :param name: str name
        :param configuration: a dict with options
        :param node_generator:

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> b = BaseNode(env, 'name_test', {'testkey':'testval'}, None)
        >>> print(b.name, b.configuration, sep=', ')
        name_test, {'testkey': 'testval'}

        """
        if configuration.get("type", False) != "SubNodeFromLink":
            BaseNode.nodes[name] = self
            BaseNode.node_list.append(self)

        self.msg_ids: List[str] = []
        self.wait_times: List[float] = []
        self.delay_till_next_msg: List[float] = []
        self.processing_times: List[float] = []
        self.data_sizes: List[float] = []
        self.time_received: List[float] = []
        self.msgs_processed: float = 0

        self.env = env
        self._name = name
        self.configuration = configuration

        self.meta_node: Optional[BaseNode] = None

        # a bit of a hack...
        self.msg_size_key: str = self.configuration.get("msg_size_key", "size_mbits")

        # created in set_node-generator function
        # self.node_exec_generator: Optional[ Generator[Tuple[float, float, List[Event]], Event, None] ] = None
        self.generates_data_only = False
        self.set_node_exec_generator(node_generator)

        self.in_pipe = None  # simpy doesn't have sigs so mypy errors are thrown : Optional[simpy.resources.store.Store]
        self.out_pipe_conns: Optional[NodePipe] = None

        self.sub_nodes: Optional[List[Any]] = None

    def get_signatures(self) -> Dict[str, Any]:
        """
        Recursive function to get all the metanodes in a one-level dict
        :return: a dict
        """
        has_meta_node = self.meta_node
        sigs: Dict[str, Any] = {}
        # Might have Meta nodes within Meta nodes
        # so need to transverse the meta_node link until a None is found
        while has_meta_node:
            meta_sigs = has_meta_node.get_signatures()
            # This order makes the meta node sigs override
            sigs = {**sigs, **meta_sigs}
            has_meta_node = has_meta_node.meta_node
        return sigs

    def record_msg(
        self,
        data_in: Event,
        data_out_list: List[Event],
        total_delay: float,
        processing_time: float,
    ) -> None:
        """
        Produce a record of a message for now store it on the base node
        :param data_in: an event
        :param data_out_list: a list of events
        :param processing_time: a float
        :return: None

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> import datetime
        >>> env.now_datetime = lambda : datetime.time(1, 23, 45)
        >>> b = BaseNode(env, 'test_name', {}, None)
        >>> b.record_msg({'ID': 'testID'}, [], 0.0)
         0.0%|    0.00|01:23:45.000000|     test_name      |[   BaseNode   ]|testID|Msg done.

        """

        # If this message came from another node mark it's time sent otherwise
        # this message originated from this node and its origin is now
        time_arrived = data_in["time_sent"] if "time_sent" in data_in else self.env.now

        if not data_in["ID"] in BaseNode.msg_history:
            # This message isn't in this node, create an empty data
            BaseNode.msg_history[data_in["ID"]] = []

        # Pull the from node
        from_node = data_in.get("last_node", self.name)

        # Add this message to this node's history
        BaseNode.msg_history[data_in["ID"]].append(
            (
                self.env.now,  # Processing start time
                self.env.now_datetime(),
                from_node,
                self.name,
                data_in.copy(),
                processing_time,
                total_delay,
                self.env.now - time_arrived,
            )
        )

        # There are no messages going out
        if not data_out_list:
            # Terminate the message
            self.record_end_of_data(data_in)

    def record_end_of_data(self, data) -> None:
        """
        prints out data parameter to log, with 'Msg done.' at the end
        :param data: a dict. must have key 'ID'
        :return: None

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> import datetime
        >>> env.now_datetime = lambda : datetime.time(5, 43, 21)
        >>> b = BaseNode(env, 'not_a_real_name', {}, None)
        >>> b.record_end_of_data({'ID': 'not_a_real_id'})
         0.0%|    0.00|05:43:21.000000|  not_a_real_name   |[   BaseNode   ]|not_a_real_id|Msg done.

        """
        print(self.log_prefix(data["ID"]) + "Msg done.")

    # Helper functions

    def log_prefix(self, id: str = "00000000-0000-0000-000000000000") -> str:
        """
        returns and does not print out the current time, and name, type of self, and ID param.

        disable this for now, end result kinda was terrabad
        however, the celery worker engine worked well

        :param id: looks like a uuid
        :return: a string with current time,

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> import datetime
        >>> env.now_datetime = lambda : datetime.time(5, 55, 55)
        >>> env.end_simtime = 100.0
        >>> b = BaseNode(env, 'base node b', {}, None)
        >>> b.log_prefix()
        ' 0.0%|    0.00|05:55:55.000000|    base node b     |[   BaseNode   ]|00000000-0000-0000-000000000000|'

        """
        now_datetime = self.env.now_datetime()
        return "{:4.1f}%|{:8.2f}|{}|{:^20}|[{:^15}]|{}|".format(
            self.env.now / self.env.end_simtime * 100.0,
            self.env.now,
            now_datetime.isoformat(timespec="microseconds"),
            self.name,
            self.__class__.__name__,
            id,
        )

    def check_for_special_variables(
        self, result: str, key_value_dict: Dict[str, str]
    ) -> str:
        """
        If somebody punted and left {NodeName} in the result string, this fixes it
        :param result: probably one of those log output things but could be any string
        :param key_value_dict: not used
        :return: result but with '{NodeName} replaced with the real name

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> b = BaseNode(env, 'the-real-name', {}, None)
        >>> b.check_for_special_variables('SimTime|    0.00| {NodeName}  |[   BaseNode   ]|00000000|', {})
        'SimTime|    0.00| the-real-name  |[   BaseNode   ]|00000000|'
        >>> b.check_for_special_variables('SimTime|    0.00| a-good-name |[   BaseNode   ]|00000000|', {})
        'SimTime|    0.00| a-good-name |[   BaseNode   ]|00000000|'

        """
        result_str = str(result)

        if "{NodeName}" in result_str:
            result = result_str.replace("{NodeName}", self._name)

        return result

    def create_history_dataframe(self) -> pd.DataFrame:
        """
        the internet states appending to a dataframes is wicked slow, so use
        lists until someone asks for the stats
        create Pandas dataframe from wait_times, processing_times, data_sizes, count lists
        :return: a dataframe. the code actually explains it well

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> import pandas as pd
        >>> b = BaseNode(env, 'the-real-name', {}, None)
        >>> b.msg_ids             = ['example_id_1', 'example_id_2']
        >>> b.time_received       = [0.1,            0.2           ]
        >>> b.wait_times          = [0.05,           1.2           ]
        >>> b.delay_till_next_msg = [2.0,            3.0           ]
        >>> b.processing_times    = [4.0,            5.0           ]
        >>> b.data_sizes          = [6.0,            7.0           ]
        >>> pd.set_option('max_columns', 10)
        >>> pd.set_option('expand_frame_repr', False)
        >>> b.create_history_dataframe()
                   UUID  Sim_time  msg_wait_time  delay_till_next_msg  processing_time  data_size
        0  example_id_1       0.1           0.05                  2.0              4.0        6.0
        1  example_id_2       0.2           1.20                  3.0              5.0        7.0

        """
        df = pd.DataFrame(
            {
                "UUID": self.msg_ids,
                "Sim_time": self.time_received,
                "msg_wait_time": self.wait_times,
                "delay_till_next_msg": self.delay_till_next_msg,
                "processing_time": self.processing_times,
                "data_size": self.data_sizes,
            }
        )
        return df

    # pipe methods
    def set_output_conn(self, pipe_conn: NodePipe) -> None:
        """
        used for tests only. sets out_pipe_cons to specified NodePipe
        :param pipe_conn:
        :return: None
        """
        self.out_pipe_conns = pipe_conn

    def set_node_exec_generator(self, node_generator) -> None:
        """
        sets node_exec_generator
        :param node_generator:
        :return: None
        """
        self.node_exec_generator = node_generator
        # tell the generator to start, it will pause when it reaches its first yield
        if self.node_exec_generator:
            self.node_exec_generator.send(None)

    def send_data_to_output(
        self, data_out_list: List[Event], processing_time: float
    ) -> Iterable[simpy.Event]:
        """
        A coroutine that puts data_out in the right outpipe at the right simtime
        Might need to mod this to take (time, out_data) tuples so output data
        can have different times from each other...maybe
        :param data_out_list:
        :param processing_time:
        :return: Iterable / Generator thing

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> import datetime
        >>> env.now_datetime = lambda : datetime.time(3, 33, 33)
        >>> b = BaseNode(env, 'test_name', {}, None)
        >>> _ = env.process(b.send_data_to_output([{'ID':'test_ID_1'}], 1.0))
        >>> _ = env.process(b.send_data_to_output([{'ID':'test_ID_2'}], 1.5))
        >>> env.run(until=2)
         1.0%|    1.00|03:33:33.000000|     test_name      |[   BaseNode   ]|test_ID_1|Msg done.
         1.5%|    1.50|03:33:33.000000|     test_name      |[   BaseNode   ]|test_ID_2|Msg done.

        """
        # Add data to data out, name and time sent
        for data_out in data_out_list:
            data_out["last_node"] = self.name
            data_out["time_sent"] = self.env.now + processing_time

        # Wait for the processing time to finish
        yield self.env.timeout(processing_time)

        # Send each output
        for data_out in data_out_list:
            if self.out_pipe_conns:
                num_routes = self.out_pipe_conns.put((self.env.now, data_out))
                if num_routes == 0:
                    self.record_end_of_data(data_out)
            else:
                # No place to send output
                self.record_end_of_data(data_out)

    def run(self) -> Iterable[simpy.Event]:
        """
        a coroutine for processing data as it arrives at the Node Inpipe,
        or Writing generated data to its outpipe
        :return: an itreable/generator thing
        """
        if self.node_exec_generator:
            while True:
                if self.in_pipe and not self.generates_data_only:
                    # Grab the data in
                    (time_arrived, data_in) = yield self.in_pipe.get()

                    # Run the node
                    (
                        delay_till_get_next_msg,
                        time_to_send_data_out,
                        data_out_list,
                    ) = self.node_exec_generator.send(data_in)
                    # Return should always be:
                    # 1. The processing time within the node, which reserves it
                    # 2. The delay for the message to arrive at the next node
                    # 3. The actual data to be sent out

                    if type(time_to_send_data_out) is float:
                        time_to_send_data_out = [time_to_send_data_out]

                    for index, out_msg in enumerate(data_out_list):
                        event_time = time_to_send_data_out[index]
                        # Ensure the delay is not negative
                        if delay_till_get_next_msg < 0.0 or event_time < 0.0:
                            print(
                                self.log_prefix(),
                                "ERROR: Node returned negative delay {} or processing time {}".format(
                                    delay_till_get_next_msg, event_time
                                ),
                            )
                            # hack for now until I figure out what is causing this
                            delay_till_get_next_msg = max(delay_till_get_next_msg, 0.0)
                            event_time = max(event_time, 0.0)

                        # log the msg and node used histories
                        self.perform_node_bookkeeping(
                            data_in["time_sent"]
                            if "time_sent" in data_in
                            else time_arrived,  # time_sent,
                            delay_till_get_next_msg,
                            event_time,
                            str(data_in["ID"]),  # UUID's don't serialize so save as string
                            data_in[self.msg_size_key],
                            [out_msg],
                        )

                        # The message has been processed, record it to log
                        self.record_msg(
                            data_in,
                            [out_msg],
                            event_time,
                            delay_till_get_next_msg,
                        )

                        # add the 'send data to our outpipe' event to the sim
                        # if there are any data to send out
                        if data_out_list:
                            simpy.events.Process(
                                self.env,
                                self.send_data_to_output([out_msg], event_time) ,
                            )

                        # wait until we are ready to process the next msg in our inbox
                        yield self.env.timeout(delay_till_get_next_msg)

                    if delay_till_get_next_msg == BaseNode.stop_signal:
                            # TODO change this to an exception
                            # stop the sim
                            return

                    # If a node doesn't have an in pipe, then it generates data only
                    yield self.env.timeout(delay_till_get_next_msg)

                # If a node doesn't have an in pipe, then it generates data only
                elif self.out_pipe_conns:
                    (
                        delay_till_get_next_msg,
                        time_to_send_data_out,
                        data_out_list,
                    ) = next(self.node_exec_generator)

                    if delay_till_get_next_msg == BaseNode.stop_signal:
                        # TODO change this to an exception
                        return

                    # assumes at least data msg is generated. Spoiler, bad assumption
                    if data_out_list:
                        self.perform_node_bookkeeping(
                            self.env.now,
                            delay_till_get_next_msg,
                            time_to_send_data_out,
                            data_out_list[0]["ID"],
                            data_out_list[0][self.msg_size_key],
                            data_out_list,
                        )
                        self.record_msg(
                            data_out_list[0],
                            data_out_list,
                            delay_till_get_next_msg,
                            time_to_send_data_out,
                        )

                        # send msgs
                        simpy.events.Process(
                            self.env,
                            self.send_data_to_output(
                                data_out_list, time_to_send_data_out
                            ),
                        )

                        # wait until processing time has been reached
                        yield self.env.timeout(delay_till_get_next_msg)
                    else:
                        # only way to get here is a node without in_pipes unexpectedly
                        # which will cause an endlessloop. For now, report it and move on
                        print(
                            self.log_prefix()
                            + "WARNING! Node %s didn't Generate any data. Check its connections."
                            % self.name
                        )

                        return

                else:
                    # This node doesn't have anything coming in, nor does it
                    # generate data.
                    print(
                        self.log_prefix()
                        + "Error: Node has no configured in or out pipes"
                    )
                    break
                ## END - DataGen or regular node
            ## END - Run forever
        ## END - Check if node

    ## END - Run

    def perform_node_bookkeeping(
        self,
        time_sent: float,
        delay_till_next_msg: float,
        processing_time: float,
        data_in_id: str,
        data_in_size: float,
        data_out_list: List[Event],
    ) -> None:
        """
        Processes the node bookkeeping to keep track of the number of messages
        processed, data processed, etc. all at the node level.

        :param time_sent: The time the message arrives at the node.
        :param delay_till_next_msg: The time at which this node can get a new message.
        :param processing_time: The amount of time this node has processed.
        :param data_in_id: The data ID
        :param data_in_size: The amount of data that has entered the node.
        :param data_out_list: The messages that have left the node.
        :return: None
        """
        if self.env.node_log:
            self.env.node_log.write(
                "{}\t{}\t{}\t{}\t{}\t{}\t{}\n".format(
                    time_sent,
                    self.name,
                    data_in_id,
                    data_in_size,
                    self.env.now - time_sent,
                    processing_time,
                    delay_till_next_msg,
                )
            )

        # This node has processed an additional message
        self.msgs_processed += 1
        # Add the message ID to the list
        self.msg_ids.append(data_in_id)  # data_in["ID"])
        # List the time received
        self.time_received.append(time_sent)
        # Delta between simulation now and the time sent.
        self.wait_times.append(self.env.now - time_sent)
        self.data_sizes.append(data_in_size)  # data_in[self.msg_size_key])
        self.delay_till_next_msg.append(delay_till_next_msg)
        self.processing_times.append(processing_time)
        if self.meta_node:
            self.meta_node.perform_node_bookkeeping(
                time_sent,
                delay_till_next_msg,
                processing_time,
                data_in_id,
                data_in_size,
                data_out_list,
            )

    # helper functions to parse strings to types
    def setBoolFromConfig(
        self, config_key: str, default: bool
    ) -> Callable[[], Optional[bool]]:
        """
        gets a bool from the configuration dict
        :param config_key: str, hopefully in self.config
        :param default: value if config_key isn't in self.config
        :return: a callable that returns a bool

        OLD CODE
        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> b = BaseNode(env, '', {'float_value': 6.0, 'str_value': '5.5'}, None)
        >>> f = b.setFloatFromConfig('float_value', 0.4)
        >>> f()
        6.0
        >>> g = b.setFloatFromConfig('str_value', 0.4)
        >>> g()
        5.5
        >>> h = b.setFloatFromConfig('no_value', 0.4)
        >>> h()
        0.4

        """
        config_string = self.configuration.get(config_key, default)
        config_value: Optional[bool]
        try:
            config_value = config_string == "True" or config_string
        except:
            config_value = None

        if config_value != None:
            return lambda: config_value
        else:
            keyvalue: Any = BaseNode.nodes[config_string]
            return lambda: bool(keyvalue.getValue())

    def setFloatFromConfig(
        self, config_key: str, default: float
    ) -> Callable[[], Optional[float]]:
        """
        gets a float from the configuration dict
        :param config_key: str, hopefully in self.config
        :param default: value if config_key isn't in self.config
        :return: a callable that returns a float

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> b = BaseNode(env, '', {'float_value': 6.0, 'str_value': '5.5'}, None)
        >>> f = b.setFloatFromConfig('float_value', 0.4)
        >>> f()
        6.0
        >>> g = b.setFloatFromConfig('str_value', 0.4)
        >>> g()
        5.5
        >>> h = b.setFloatFromConfig('no_value', 0.4)
        >>> h()
        0.4

        """
        # Check the configuration for the key
        config_string = self.configuration.get(config_key, default)
        config_value: Optional[float]

        # Ensure type
        try:
            config_value = float(config_string)
        except:
            config_value = None

        # If this key was not found, check to see if there's a node a value
        # can be pulled from with a .getValue function.
        if config_value != None:
            return lambda: config_value
        else:
            keyvalue: Any = BaseNode.nodes[config_string]
            return lambda: float(keyvalue.getValue())

    def setIntFromConfig(
        self, config_key: str, default: int
    ) -> Callable[[], Optional[int]]:
        """
        gets an int from the configuration dict
        :param config_key: str, hopefully in self.config
        :param default: value if config_key isn't in self.config
        :return: a callable that returns an int

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> b = BaseNode(env, '', {'int_value': 6, 'str_value': '5', 'flt_val': 5.5}, None)
        >>> f = b.setIntFromConfig('int_value', -1)
        >>> f()
        6
        >>> g = b.setIntFromConfig('str_value', -1)
        >>> g()
        5
        >>> h = b.setIntFromConfig('no_value', -1)
        >>> h()
        -1
        >>> k = b.setIntFromConfig('flt_val', -1)
        >>> k()
        5

        """
        config_string = self.configuration.get(config_key, default)
        config_value: Optional[int]
        try:
            config_value = int(config_string)
        except:
            config_value = None
        if config_value:
            return lambda: config_value
        else:
            value_str: Any = BaseNode.nodes[config_string]
            return lambda: int(value_str.getValue())

    def setStringFromConfig(
        self, config_key: str, default: str
    ) -> Callable[[], Optional[str]]:
        """
        gets a str from the configuration dict.
        :param config_key: str, hopefully in self.config
        :param default: value if config_key isn't in self.config
        :return: a callable that returns an str

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> b = BaseNode(env, '', {'value_1': 'abcd', 'value_2': 5}, None)
        >>> BaseNode.nodes = {'name': 'node'}
        >>> f = b.setStringFromConfig('value_1', 'null')
        >>> f()
        'abcd'
        >>> g = b.setStringFromConfig('value_2', 'null')
        >>> g()
        '5'
        >>> h = b.setStringFromConfig('no_value', 'null')
        >>> h()
        'null'

        """
        config_string = self.configuration.get(config_key, default)
        if config_string in [name for name in BaseNode.nodes]:
            value: Any = BaseNode.nodes[config_string]
            return lambda: value.getValue()
        else:
            return lambda: str(config_string)

    def setLiteralFromConfig(
        self, config_key: str, default: str
    ) -> Callable[[], Optional[Any]]:
        """
        gets a literal from the configuration dict. breaks the pattern with name 'get...' instead of 'set...'
        :param config_key: str, hopefully in self.config
        :param default: value if config_key isn't in self.config
        :return: a callable that returns an str

        >>> from source.python_lib.Nodes.BaseNode import BaseNode
        >>> b = BaseNode(env, '', {'value_1': '[1, 2, 3, 4]'}, None)
        >>> BaseNode.nodes = {'name': 'node'}
        >>> f = b.setLiteralFromConfig('value_1', 'null')
        >>> f()
        [1, 2, 3, 4]
        >>> g = b.setLiteralFromConfig('no_value', 'null')
        >>> g()
        'null'

        """
        config_string = self.configuration.get(config_key, default)
        try:
            config_value = ast.literal_eval(config_string)
        except:
            config_value = default
        return lambda: config_value
