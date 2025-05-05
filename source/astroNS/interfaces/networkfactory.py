"""
NetworkFactory provides the methods to read a network file and generate the
initial network design to be run within the tool.

"""

import configparser
import simpy
import yaml
import json

from links import *
from links.predicates import patterns
from nodes import *
from common.left_side_value import left_side_value

node_factory = {cls.__name__.lower(): cls for cls in BaseNode.__subclasses__()}

#
# loaded nodes will have the following:
#   name, type, config fields unique to type, out connections to other nodes (as fields)
#
# To extend additional foo nodes, add 'from Nodes.foo import *' to the top of this file

# generates something like this with magic:
# node_factory = {
#                  'DelaySize'        : DelaySize,
#                  'Processor'        : Processor,
#                  'FileDataReader'   : FileDataReader,
#                  'RandomDataGen'    : RandomDataGen,
#                  'Router'           : Router,
#                  'ExcelDataReader'  : ExcelDataReader,
#                  'AdderNode'        : AdderNode,
#                  'RandomDistribNode': RandomDistribNode,
#                  'DelayTime'        : DelayTime,
#                  'PhysicsLib_Functions': PhysicsLib_Functions
#               }


def load_network_file(filename, env, meta_node=None):
    """Determines how the file should be read, based on filetype

    Args:
        filename: The filename for the network model.
        env: The simpy environment class.
        meta_node (bool, optional): Whether this node is a meta node or not.

    Returns:
        The result of a selected method of parsing the filename

    """

    if filename.endswith(".ini"):
        return load_config_file(filename, env, meta_node)
    if filename.endswith(".json"):
        with open(filename, "r") as jsonfile:
            json_string = jsonfile.read()

        return load_json_string(json_string, env, meta_node)
    if filename.endswith(".yml"):
        with open(filename, "r") as ymlfile:
            yaml_string = ymlfile.read()
        return load_yml_string(yaml_string, env, meta_node)

    raise NotImplementedError(
        "Could not parse unknown file type. Accepted types are [ini, json, yml]"
    )


################################################################################


def load_json_string(json_string, env, meta_node=None):  # ''
    """Loads the network based on json formatting.

    Args:
        json_string: A string of json that defines the network
        env: The simpy environment class.

    Returns:
        The result of a selected method of parsing the filename

    """
    parsed_json = json.loads(json_string)
    if "nodes" in parsed_json.keys():
        parsed_json = from_D3_to_internal_json(parsed_json)
        parsed_json = json.loads(parsed_json)["network"]

    nodes = [
        (node_name.strip(), parsed_json[node_name.strip()]) for node_name in parsed_json
    ]
    network = create_network(nodes, env, meta_node)

    # save input from generators
    if meta_node:
        parsed_json = json.loads(
            '{} "{}":{} {}'.format("{", meta_node.name, json_string, "}")
        )
    env.loaded_network_json.append(parsed_json)

    return network


################################################################################


def load_config_file(filename, env, meta_node=None):
    """Loads the file based on the "ConfigParser" module in python

    Args:
        filename: The filename for the network model.
        env: The simpy environment class.
        meta_node (optional): Whether this node is a meta node or not.

    Returns:
        The result of a selected method of parsing the filename

    """
    config = configparser.ConfigParser()
    config.read(filename)
    # Cannot verify this works for NS2-31
    nodes = [
        (config[section].name.strip(), config[section]) for section in config.sections()
    ]
    return create_network(nodes, env, meta_node)


################################################################################


def load_yml_string(yaml_string, env, meta_node=None):
    """Loads the file based on the YAML method. It does not expect the file
    to be configured like the D3 model of links and nodes in separate
    keys.

    Args:
        filename: The filename for the network model.
        env: The simpy environment class.
        meta_node (optional): Whether this node is a meta node or not.

    Returns:
        The result of a selected method of parsing the filename

    """
    dictionary = yaml.safe_load(yaml_string)
    nodes = [(node.strip(), dictionary[node.strip()]) for node in dictionary.keys()]
    return create_network(nodes, env, meta_node)


################################################################################


def create_network(nodes, env, meta_node):
    """Determines how the file should be read, based on filetype

    Args:
        nodes (dict): All nodes parsed by the method, attached to the nodes is a pointer
            to the node for a pipe to be generated
        env (simpy.Environment): The simpy environment class.
        meta_node (bool): Whether this node is a meta node or not.

    Returns:
        new_nodes (list): The connected network as a list of classes
    """
    new_nodes = []
    default_dict = {}

    for name, node_dict in nodes:  # NOTE: might need ot sort this...
        if name == "DEFAULT":
            default_dict = node_dict
            continue
        else:
            # default key/values does not overwrite original key/values if they in this order
            node_dict = {**default_dict, **node_dict}

        if meta_node:
            override_dict = meta_node.overrides.get(name, {})
            # we want the original keys to be overwritten this time
            node_dict = {**node_dict, **override_dict}

        node_type = node_dict.get("type", None)

        if node_type is None:
            print(node_dict)
            raise AttributeError("The node was not found.")

        node_type = node_type.lower()

        new_node_fn = node_factory.get(node_type, None)
        if new_node_fn is None:
            print(node_factory)
            raise AttributeError(
                "ERROR: Node type {} not loaded in Factory".format(node_type)
            )

        if new_node_fn != "MISSING":
            # print('found node type: %s, creating %s' % (node_type,name))
            configuration_map = node_dict
            new_node = new_node_fn(env, name, configuration_map)
            # if node_type == 'metanode':
            if new_node.sub_nodes:
                new_nodes.extend(new_node.sub_nodes)
            else:
                new_nodes.append(new_node)

    # Connect the node via pipes
    hook_up_node_pipes(new_nodes, env, meta_node)

    return new_nodes


# returns a predicate that accept a dict and returns a bool
def parse_predicate(route_options):
    """Use the defined function to determine if the message continues

    Used when setting up a link from :func:`interfaces.networkfactory.hook_up_node_pipes`
    :param route_options: The method to lookup
    :return: function result or error
    """
    for pattern, fn in patterns:
        try:
            # Search if this data matches this pattern
            match_result = pattern.search(route_options)
            if match_result:
                return fn(match_result.groups(), left_side_value)
        except Exception as e:
            print(e)
            match_result = False
    # if reached here then none of the router fns matched
    # check to see if the option is a meta subnode
    print("ERROR: Condition didn't parse correctly: {}".format(route_options))
    exit(1)
    # return lambda data_dict:  True


def hook_up_node_pipes(nodes, env, meta_node):
    """Generates the "simpy stores" or links between nodes and how to handle
    data between nodes.

    Essentially, a link is a "simpy Store" object where out nodes will store
    in all outgoing stores and input nodes will read from the Store object.

    Args:
        nodes (list): The list of node classes from create_network
        env (simpy.Environment): The simpy environment class.
        meta_node (bool): Whether this node is a meta node or not.

    Returns:
        None

    """
    # make a map of none_names to the node instances, remove sublink nodes
    dont_map_list = [MetaNode]
    node_map = {
        node.name.lower(): node for node in nodes if type(node) not in dont_map_list
    }
    # work over the list, making a pipe for each connection
    # import pudb; pu.db
    # with open("Results/{}/graph-easy-model.txt".format(env.this_runs_uuid),"a") as grapheasyfile:
    for from_node_ in nodes:
        from_node = from_node_

        for key in from_node_.configuration.keys():
            if key.lower() in node_map.keys():
                to_node = node_map[key.lower()]

                if to_node.in_pipe:
                    # Reuse the existing pipe
                    in_pipe = to_node.in_pipe
                else:
                    in_pipe = simpy.resources.store.Store(env)
                    to_node.in_pipe = in_pipe

                if from_node.out_pipe_conns:
                    # Reuse the existing pipe
                    out_pipe = from_node.out_pipe_conns
                else:
                    out_pipe = NodePipe(env)
                    from_node.out_pipe_conns = out_pipe

                #  parse Routing options
                route_options = from_node_.configuration[key]
                if route_options:
                    # assume its a Predicate
                    from_node.configuration[key] = route_options

                    predicateFn = parse_predicate(route_options)
                    from_node.out_pipe_conns.add_output_conn(
                        in_pipe, predicateFn, predicate_string=route_options
                    )
                else:
                    # connect it as a basic pipe
                    from_node.out_pipe_conns.add_output_conn(in_pipe)

                # for debugging
                # print( '[{}] ----> {} label:"{}";{} [{}]'.format( from_node.name, '{', route_options,'}', to_node.name) )
                meta_name = meta_node.name + "/" if meta_node else ""
