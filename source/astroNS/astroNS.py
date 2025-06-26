#!/usr/bin/env python3
"""
astroNS simulator
"""

import simpy

import argparse
import pandas as pd
import datetime
import pytz
import random
import uuid
import os
import sys
import json

from multiprocessing import Queue, Process

from collections import namedtuple
from contextlib import redirect_stdout
from typing import List, Dict, Tuple

#
# Main Simulation Controller
#

# takes a:
#   Network Parser
#   Input/Data Genertors
#


def runSim(
    filename: str, simStop: float, env: simpy.Environment
) -> Tuple[List["BaseNode"], simpy.Environment]:
    """Runs the simulation

    Args:
        filename: The filename for the network model.
        simStop: The length of the scenario to run.
        env: The simpy environment class.

    Returns:
        network_nodes: The nodes to be run.
        env: The simpy environment class.

    """

    from nodes.core.base import BaseNode
    from interfaces.networkfactory import load_network_file
    from interfaces.outputdatawriter import output_loaded_config

    # Load in the file
    network_nodes = load_network_file(filename, env, None)

    # Connect the nodes
    BaseNode.make_link_map_data(network_nodes)

    # Put the nodes back in the environment for simpy
    env.network_nodes = network_nodes

    #!TODO Convert to logger instead of print
    print(
        "    %|     0.00|2020-10-22T20:58:17.862886+00:00|      astroNS     |[   Simulator   ]|00000000-0000-0000-000000000000|Loaded |{}| total nodes".format(
            len(network_nodes)
        )
    )

    # Save the configuration to file
    with open(
        "{}/loaded_node_config.txt".format(env.path_to_results), "w"
    ) as node_config_file:
        output_loaded_config(network_nodes, node_config_file, env)

    #try:
        # Run it
    env.run(until=simStop)
        #except RuntimeError:
        #print("Simulation process is too slow for real time mode. Stopping.")

    return network_nodes, env


# default args part converts a dict to an pythonobject like the args class from __main__
def setup_env(env, args):
    """Sets up the simpy environment for a discrete event simulation

    Args:
        env: The simpy environment class.
        args: Argument class object.

    """

    # this copies all the fields of 'args' into the 'env' object
    env.__dict__.update(args.__dict__)

    # Set the network name
    env.network_name = args.model_file

    # Set the epoch for the start of the scenario
    env.epoch = datetime.datetime.strptime(args.epoch, "%Y-%m-%dT%H:%M:%S.%fZ")
    env.epoch = env.epoch.replace(tzinfo=pytz.UTC)

    # No idea what this does
    env.now_datetime = lambda sim_time=None: env.epoch + datetime.timedelta(
        seconds=sim_time if sim_time else env.now
    )

    # More timestamps?
    env.start_datetime = env.now_datetime(0).isoformat(timespec="microseconds")
    env.end_simtime_dt = env.now_datetime(env.end_simtime)

    # Forces node stats to True as well
    if args.node_stats_history:
        env.make_node_stats = True

    # helps to make the output tables well formatted
    pd.set_option("display.width", 150)

    # make a token for this run
    env.this_runs_uuid = uuid.uuid4()

    # More timestamps?
    env.start_datetime = env.now_datetime(0).isoformat(timespec="microseconds")
    env.end_simtime_dt = env.now_datetime(env.end_simtime)

    # Output directory
    path_to_results = "./Results/{}{}".format(
        args.network_name,
        env.now_datetime(0)
        .replace(tzinfo=None)
        .isoformat(timespec="microseconds")
        .replace(":", "-")
        .replace(".", "_"),
    )
    if not os.path.exists(path_to_results):
        os.makedirs(path_to_results)

    env.path_to_results = path_to_results

    # Set the random seed
    if args.seed:
        seed = args.seed
    else:
        seed = random.randrange(sys.maxsize)

    # Uses random...
    random.seed(a=seed, version=2)

    env.seed = seed
    env.loaded_network_json = []

    if args.promise_threads > 0:
        job_queue = Queue()


def postprocess_network(env):
    """Post Process

    Args:
        env: The simpy environment class.
        args: Dictionary of all arguments to be passed.

    """
    from nodes.core.base import BaseNode
    from interfaces.outputdatawriter import (
        output_node_stats,
        output_msg_history,
        output_msg_history_tab,
        output_sim_end_state,
    )

    # Write the network to file
    with open(
        "{}/loaded_network.json".format(env.path_to_results), "w"
    ) as loaded_network_json_file:
        loaded_network_json_file.write(json.dumps(env.loaded_network_json, indent=2))

    if env.node_stats:
        with open(
            "{}/node_stats.txt".format(env.path_to_results), "w"
        ) as node_stats_file:
            with open(
                "{}/node_stats_total.txt".format(env.path_to_results), "w"
            ) as total_node_stats_file:
                output_node_stats(
                    env.network_nodes, node_stats_file, env.node_stats_history
                )

    with open(
        "{}/msg_history.txt".format(env.path_to_results), "w"
    ) as msg_history_file:
        output_msg_history(BaseNode.msg_history, msg_history_file)

    with open(
        "{}/msg_history.csv".format(env.path_to_results), "w"
    ) as msg_history_file:
        output_msg_history_tab(BaseNode.msg_history, msg_history_file)

    if env.final_node_states:
        with open(
            "{}/sim_end_state.txt".format(env.path_to_results), "w"
        ) as sim_end_state_file:
            output_sim_end_state(env, sim_end_state_file)

    print(
        " 100%|{:8.2f}|{}|      astroNS       |[   Simulator   ]|00000000-0000-0000-000000000000|Session token: {}".format(
            env.now,
            env.now_datetime().isoformat(timespec="microseconds"),
            env.this_runs_uuid,
        )
    )
    print(
        " 100%|{:8.2f}|{}|      astroNS       |[   Simulator   ]|00000000-0000-0000-000000000000|Done.".format(
            env.now, env.now_datetime().isoformat(timespec="microseconds")
        )
    )


class Arguments:
    def __init__(
        self,
        model_file,
        seed,
        end_simtime,
        epoch,
        terminal,
        node_stats,
        node_stats_history,
        initial_node_states,
        final_node_states,
        real_time_mode,
        real_time_strict,
        real_time_factor,
        network_name,
        promise_threads,
    ):
        self.model_file = model_file
        self.seed = seed
        self.end_simtime = end_simtime
        self.epoch = epoch
        self.terminal = terminal
        self.node_stats = node_stats
        self.node_stats_history = node_stats_history
        self.inital_node_states = initial_node_states
        self.final_node_states = final_node_states
        self.real_time_mode = real_time_mode
        self.real_time_strict = real_time_strict
        self.real_time_factor = real_time_factor
        self.network_name = network_name
        self.promise_threads = promise_threads


def main(
    model_file,
    seed=9001,
    end_simtime=200,
    epoch=datetime.datetime.now().isoformat() + "Z",
    terminal=False,
    node_stats=False,
    node_stats_history=False,
    initial_node_states=False,
    final_node_states=False,
    real_time_mode=False,
    real_time_strict=False,
    real_time_factor=1.0,
    network_name="Default_",
    promise_threads=0,
):
    """Main thread

    Args:
        model_file: File that contains the network model. Can be an .yml, .json
        seed: integer used to set the random stream number of desired
        end_simtime: runs sim until this SimTime is reached.
        epoch: Sim Start Date/Time. Defaults to now.
        terminal: writes the log to the terminal instead of the output file
        node_stats: Writes out Node stats data.
        node_stats_history: Writes out Node stats data and lists the first/last 30 messages to the node.
        initial_node_states: Write initial node state to file before sim is run
        final_node_states: Write initial node state to file before sim is run
        real_time_mode: runs the sim via real_time clock mode
        real_time_strict: if set, throws an error if a process takes more actual time than given in real time mode.
        real_time_factor: determines time unit for real_time mode. Default 1 unit = one second
        promise_threads: creates multiprocessing threads to parallelize node promises
    """

    # env required by the simpy frameworks
    env = (
        simpy.rt.RealtimeEnvironment(strict=real_time_strict)
        if real_time_mode
        else simpy.Environment()
    )

    args = Arguments(
        model_file,
        seed,
        end_simtime,
        epoch,
        terminal,
        node_stats,
        node_stats_history,
        initial_node_states,
        final_node_states,
        real_time_mode,
        real_time_strict,
        real_time_factor,
        network_name,
        promise_threads,
    )

    # configure the environment
    setup_env(env, args)

    print(
        "   0%|     0.00|{}|      astroNS      |[   Simulator   ]|00000000-0000-0000-000000000000|Session token: {}".format(
            env.start_datetime, env.this_runs_uuid
        )
    )

    # change the where to be an UUID representing the run

    # Setup the output log file, don't use system logging until we can figure out
    # how to play nice with celery logging
    with open("{}/simulation.log".format(env.path_to_results), "w") as sim_log:
        with open("{}/node_log.txt".format(env.path_to_results), "w") as node_log:
            env.node_log = node_log
            env.node_log.write(
                "SimTime\tNode\tData_ID\tData_Size\tWait_time\tProcessing_time\tDelay_to_Next\n"
            )

            orig_stdout = sys.stdout
            if not args.terminal:
                sys.stdout = sim_log

            print(
                "   0%|     0.00|{}|      astroNS      |[   Simulator   ]|00000000-0000-0000-000000000000|Using Random seed: {}".format(
                    env.start_datetime, env.seed
                )
            )
            print(
                "   0%|     0.00|{}|      astroNS      |[   Simulator   ]|00000000-0000-0000-000000000000|Session token: {}".format(
                    env.start_datetime, env.this_runs_uuid
                )
            )

            filename = args.model_file
            SimStop = args.end_simtime



            network_nodes, env = runSim(filename, SimStop, env)

            print(
                " 100%|{:8.2f}|{}|      astroNS       |[   Simulator   ]|00000000-0000-0000-000000000000|Session token: {}".format(
                    env.now,
                    env.now_datetime().isoformat(timespec="microseconds"),
                    env.this_runs_uuid,
                )
            )
            sys.stdout = orig_stdout

    # grab all of the stats at the end of the simulation
    postprocess_network(env)


# Run this code if called directly
if __name__ == "__main__":
    import fire

    fire.Fire(main)
