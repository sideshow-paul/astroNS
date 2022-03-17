"""
NodePipe provides connectivity between nodes in the network.
"""


import simpy
import itertools
import random


class NodePipe(object):
    """NodePipe class"""

    def __init__(self, env, capacity=simpy.core.Infinity):
        """Initialize a NodePipe"""
        self.env = env
        self.capacity = capacity
        self.pipes = []
        self.predicates_to_pipe = []
        self.predicates_to_string = {}

    def put(self, value):
        """Puts message in the outgoing simpy stores.
        :param value: Value to put in the store
        :return: float number of pipes messages were stored
        """
        if not self.pipes and not self.predicates_to_pipe:
            raise RuntimeError("There are no output pipes")
        # place copy of message in Redis stream?

        # Routing
        # insert a random number into the value dict so percentage_routes checks can work
        value[1]["random_router_value"] = random.randint(0, 100)
        value[1]["__SimTime__"] = value[0]

        route_pred = [
            store.put(value)
            for predicate, store in self.predicates_to_pipe
            if predicate(value)
        ]
        route_always = [store.put(value) for store in self.pipes]

        route_all = itertools.chain(route_pred, route_always)

        self.env.all_of(route_all)
        return len(route_pred) + len(route_always)

    def add_output_conn(self, pipe, predicate=None, predicate_string=""):
        """Adds output connection to node.

        Attaches the pipe along with any routing function if required to send
        messages through the pipe.

        :param pipe: The pipe to add
        :param predicate: A router function if needed
        :param predicate_string: The string value if needed
        """
        if predicate:
            self.predicates_to_pipe.append((predicate, pipe))
            self.predicates_to_string[predicate] = predicate_string
        else:
            self.pipes.append(pipe)

    # Not used anymore, work moved to Networkfactory:hook_up_node_pipes
    def get_output_conn(self, predicate=None):
        """Deprecated"""
        pipe = simpy.Store(self.env, capacity=self.capacity)
        if predicate:
            self.predicates_to_pipe.append((predicate, pipe))
        else:
            self.pipes.append(pipe)
        return pipe

    def __repr__(self):
        return "<NodePipe: pipes: %s>" % (self.pipes)
