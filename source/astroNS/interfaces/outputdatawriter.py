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
    """Output node stats to file, doesn't seem to be used right now. This will
    process overall stats rather than just individual nodes.

    Args:
        nodes (list): The list of all node classes
        file_stream: Place all file output in this stream.

    Returns:
        None
    """

    pd.set_option("expand_frame_repr", False)
    pd.set_option("display.max_rows", 9999)
    pd.set_option("display.max_colwidth", 100)

    index = [node.name for node in nodes]

    filtered_list = [node.create_history_dataframe() for node in nodes]

    data_size_sum_list = []
    data_size_mean_list = []
    data_size_std_list = []

    wait_time_sum_list = []
    wait_time_mean_list = []
    wait_time_std_list = []

    processing_time_sum_list = []
    processing_time_mean_list = []
    processing_time_std_list = []

    for df in filtered_list:
        data_size_sum_list.append(df["data_size"].sum())
        data_size_mean_list.append(df["data_size"].mean())
        data_size_std_list.append(df["data_size"].std())

        wait_time_sum_list.append(df["msg_wait_time"].sum())
        wait_time_mean_list.append(df["msg_wait_time"].mean())
        wait_time_std_list.append(df["msg_wait_time"].std())

        processing_time_sum_list.append(df["processing_time"].sum())
        processing_time_mean_list.append(df["processing_time"].mean())
        processing_time_std_list.append(df["processing_time"].std())

    total_df = pd.DataFrame(
        {
            "sum_size": data_size_sum_list,
            "mean_size": data_size_mean_list,
            "std_size": data_size_std_list,
            "sum_wait_time": wait_time_sum_list,
            "mean_wait_time": wait_time_mean_list,
            "std_wait_time": wait_time_std_list,
            "sum_processing_time": processing_time_sum_list,
            "mean_processing_time": processing_time_mean_list,
            "std_processing_time": processing_time_std_list,
        },
        index=index,
    )
    file_stream.write(str(total_df))

    sum_data_plot_data = pd.DataFrame({"sum_size": data_size_sum_list}, index=index)


def output_node_stats(nodes, file_stream, write_history=False):
    """Output individual node stats.

    Args:
        nodes (list): The list of all node classes
        file_stream: Place all file output in this stream.
        write_history (bool): Whether to output node history as well

    Returns:
        None
    """
    filtered_list = [node for node in nodes]
    for node in filtered_list:
        df = node.create_history_dataframe()
        # history_string = str(df)
        stats_df = pd.concat(
            [
                df.describe(),
                df.agg(
                    {
                        "data_size": sum,
                        "delay_till_next_msg": ["sum"],
                        "msg_wait_time": sum,
                        "processing_time": sum,
                    }
                ),
            ],
            sort=True,
        )
        file_stream.write("\n\nNode: {}".format(node.name))
        file_stream.write("\n" + str(stats_df))
        if write_history:
            history_string = str(df)
            file_stream.write("\nNode History")
            file_stream.write("\n" + history_string)


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

    Args:
        nodes (list): The list of all node classes
        file_stream: Place all file output in this stream.

    Returns:
        None
    """
    for node in nodes:
        df = node.create_history_dataframe()
        stats_df = pd.concat(
            [
                df.describe(),
                df.agg(
                    {
                        "data_size": sum,
                        "delay_till_next_msg": ["sum"],
                        "msg_wait_time": sum,
                        "processing_time": sum,
                    }
                ),
            ]
        )
        history_string = df.to_json()  # str(df)
        stats_string = stats_df.describe().to_json()

        file_stream.write('{} "{}:"'.format("{", node.name))
        file_stream.write("\n" + stats_string)
        file_stream.write("\nNode History")
        file_stream.write("\n" + history_string)


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
