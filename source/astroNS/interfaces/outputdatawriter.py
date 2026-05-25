"""Output_Data_Writer contains all functions associated with output including
logging and statistics.

"""
import pprint
import pandas as pd
import yaml


def output_loaded_config(nodes, file_stream, env):
    """Intended to output the configuration after loading to allow an analyst
    to ensure all nodes were loaded correctly due to spelling mistakes or other
    input errors.

    Args:
        nodes (list): The list of node classes from create_network
        file_stream: Place all file output in this stream.
        env (simpy.Environment): The simpy environment class.

    Returns:
        None

    """
    pass


def output_node_overall_stats(nodes, file_stream):
    """Output overall stats summary across all nodes.

    Uses StreamingStats (get_stats()) — works in lean_mode with O(1) memory.

    Args:
        nodes (list): The list of all node classes
        file_stream: Place all file output in this stream.

    Returns:
        None
    """
    index = []
    rows = []
    for node in nodes:
        stats = node.get_stats()
        ds = stats["data_size"]
        wt = stats["wait_time"]
        pt = stats["processing_time"]
        index.append(node.name)
        rows.append({
            "sum_size": ds["sum"],
            "mean_size": ds["mean"],
            "std_size": ds["std"],
            "sum_wait_time": wt["sum"],
            "mean_wait_time": wt["mean"],
            "std_wait_time": wt["std"],
            "sum_processing_time": pt["sum"],
            "mean_processing_time": pt["mean"],
            "std_processing_time": pt["std"],
        })

    total_df = pd.DataFrame(rows, index=index)
    pd.set_option("expand_frame_repr", False)
    pd.set_option("display.max_rows", 9999)
    file_stream.write(str(total_df))


def output_node_stats(nodes, file_stream, write_history=False):
    """Output individual node stats.

    Uses StreamingStats (get_stats()) for summary statistics — works in both
    lean_mode and normal mode with O(1) memory. The write_history option
    still requires lean_mode=False (legacy list accumulators).

    Args:
        nodes (list): The list of all node classes
        file_stream: Place all file output in this stream.
        write_history (bool): Whether to output node history as well

    Returns:
        None
    """
    for node in nodes:
        stats = node.get_stats()
        file_stream.write("\n\nNode: {}".format(node.name))
        file_stream.write("\n  Messages processed: {}".format(stats["msgs_processed"]))

        for metric_name, metric_key in [
            ("Wait Time", "wait_time"),
            ("Processing Time", "processing_time"),
            ("Delay", "delay"),
            ("Data Size", "data_size"),
        ]:
            s = stats[metric_key]
            file_stream.write("\n  {}:".format(metric_name))
            file_stream.write(
                "\n    count={count}  mean={mean:.6f}  std={std:.6f}"
                "  min={min:.6f}  max={max:.6f}  sum={sum:.6f}".format(**s)
            )
            file_stream.write(
                "\n    p25={p25:.6f}  p75={p75:.6f}  p90={p90:.6f}".format(**s)
            )

        if write_history:
            try:
                df = node.create_history_dataframe()
                file_stream.write("\nNode History")
                file_stream.write("\n" + str(df))
            except Exception:
                file_stream.write("\n  (history not available — lean_mode enabled?)")


def output_msg_history(msg_history, file_stream):
    """Output message history for each message.

    Display for each movement of the message: time, source node, end node,
    "new_data_list", and processing time.

    Args:
        msg_history (dict): History of all messages
        file_stream: Place all file output in this stream.

    Returns:
        None
    """
    file_stream.write("\n\nMsg History")
    for id in msg_history.keys():
        file_stream.write("\nMsg: " + str(id))
        for (
            time,
            time_datetime,
            from_node,
            visited_node,
            new_data_list,
            processing_time,  # time this node was reserved
            total_delay,  # time before the node hits the next node
            delay,  # time after the node hit this node that it waited
        ) in msg_history[id]:
            file_stream.write(
                "\n{:f} {} -- {} --> {} {} {}".format(
                    time,
                    time_datetime.isoformat(timespec="microseconds"),
                    from_node,
                    processing_time,
                    visited_node,
                    new_data_list,
                )
            )
        file_stream.write("\n")


def output_msg_history_tab(msg_history, file_stream):
    """Output message history for each message.

    Display for each movement of the message: time, source node, end node,
    "new_data_list", and processing time.

    Args:
        msg_history (dict): History of all messages
        file_stream: Place all file output in this stream.

    Returns:
        None
    """
    # Set header
    header = (
        "id,msg_wait,simtime,datetime,processing,delay,origin," + "destination,data"
    )
    file_stream.write(header)
    for id in msg_history.keys():
        for (
            time,
            time_datetime,
            from_node,
            visited_node,
            new_data_list,
            processing_time,  # time this node was reserved
            total_delay,  # time before the node hits the next node
            delay,  # time after the node hit this node that it waited
        ) in msg_history[id]:
            file_stream.write(
                "\n{},{},{},{},{},{},{},{},{}".format(
                    str(id),
                    delay,
                    time,
                    time_datetime.isoformat(timespec="microseconds"),
                    processing_time,
                    total_delay - processing_time,
                    from_node,
                    visited_node,
                    yaml.dump(new_data_list, encoding=("utf-8")),
                )
            )


def output_sim_end_state(env, file_stream):
    """Output sim state at the end of the simulation.

    Output the state of all nodes at the end of the simulation. Particularly
    useful if nodes have a state associated with them.

    Args:
        env (simpy.Environment): The simpy environment variable
        file_stream: Place all file output in this stream.

    Returns:
        None
    """
    pp = pprint.PrettyPrinter(indent=3, stream=file_stream)
    pp.pprint(vars(env))
    pp.pprint("\nNode Configuration")
    for node in env.network_nodes:
        pp.pprint(vars(node))


def loaded_config_to_json(nodes, file_stream):
    """Json output version of :func:`output_loaded_config`

    Args:
        nodes (list): The list of all node classes
        file_stream: Place all file output in this stream.

    Returns:
        None
    """
    pp = pprint.PrettyPrinter(indent=3)
    for node in nodes:
        file_stream.write("\n" + node.name + "\n")
        file_stream.write(pp.pformat(vars(node)) + "\n")


def output_node_stats_json(nodes, file_stream):
    """Json output version of :func:`output_node_stats`

    Uses StreamingStats (get_stats()) — works in lean_mode with O(1) memory.

    Args:
        nodes (list): The list of all node classes
        file_stream: Place all file output in this stream.

    Returns:
        None
    """
    import json

    results = {}
    for node in nodes:
        results[node.name] = node.get_stats()

    file_stream.write(json.dumps(results, indent=2))


def output_msg_history_json(msg_history, file_stream):
    """Json output version of :func:`output_msg_history`

    Args:
        nodes (list): The list of all node classes
        file_stream: Place all file output in this stream.

    Returns:
        None
    """
    file_stream.write("\n\nMsg History")
    for id in msg_history.keys():
        file_stream.write("\nMsg: " + str(id))
        for (
            time,
            time_datetime,
            visited_node,
            new_data_list,
            processing_time,
        ) in msg_history[id]:
            file_stream.write(
                "\n{:f} {} {} {} {}".format(
                    time,
                    time_datetime.isoformat(timespec="microseconds"),
                    visited_node,
                    new_data_list,
                    processing_time,
                )
            )
        file_stream.write("\n")


def output_sim_end_state_json(env, file_stream):
    """Json output version of :func:`output_sim_end_state`

    Args:
        env (simpy.Environment): The simpy environment variable
        file_stream: Place all file output in this stream.

    Returns:
        None
    """
    pp = pprint.PrettyPrinter(indent=3, stream=file_stream)
    pp.pprint(vars(env))
