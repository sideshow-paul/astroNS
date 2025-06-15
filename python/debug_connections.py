#!/usr/bin/env python3
"""
Debug script to verify connection parsing in YAML network diagrams.
"""

import yaml
import sys
from pathlib import Path


def debug_parse_yaml(yaml_file):
    """Parse YAML and print all detected connections."""
    
    # Read YAML file
    with open(yaml_file, 'r') as f:
        yaml_content = yaml.safe_load(f)
    
    # Collect all node names (excluding DEFAULT)
    all_node_names = set(key for key in yaml_content.keys() if key != 'DEFAULT')
    
    print(f"Found {len(all_node_names)} nodes: {', '.join(sorted(all_node_names))}")
    print("\nConnections found:")
    print("-" * 50)
    
    connections = []
    
    # Parse nodes and their connections
    for node_name, node_config in yaml_content.items():
        if node_name == 'DEFAULT':
            continue
            
        if isinstance(node_config, dict):
            # Find connections - any sub-key that matches a node name is a connection
            for key, value in node_config.items():
                if key in all_node_names:
                    # This key is a node name, so it's a connection
                    if value is None:
                        label = f"{key}: ~"
                    elif isinstance(value, str):
                        # Check if it's just a tilde or empty
                        if value.strip() in ['~', '']:
                            label = f"{key}: ~"
                        else:
                            # It has a condition or value
                            label = f"{key}: {value}"
                    else:
                        # Non-string value (could be bool, number, etc.)
                        label = f"{key}: {value}"
                    
                    connections.append((node_name, key, label))
                    print(f"{node_name} -> {key} [{label}]")
    
    print("-" * 50)
    print(f"Total connections: {len(connections)}")
    
    # Analyze node connectivity
    print("\nNode connectivity analysis:")
    print("-" * 50)
    
    outgoing = {}
    incoming = {}
    
    for from_node, to_node, _ in connections:
        outgoing[from_node] = outgoing.get(from_node, 0) + 1
        incoming[to_node] = incoming.get(to_node, 0) + 1
    
    for node in sorted(all_node_names):
        out_count = outgoing.get(node, 0)
        in_count = incoming.get(node, 0)
        print(f"{node}: {in_count} incoming, {out_count} outgoing")
    
    # Find root nodes (no incoming) and leaf nodes (no outgoing)
    root_nodes = [node for node in all_node_names if node not in incoming]
    leaf_nodes = [node for node in all_node_names if node not in outgoing]
    
    print(f"\nRoot nodes (no incoming): {', '.join(root_nodes) if root_nodes else 'None'}")
    print(f"Leaf nodes (no outgoing): {', '.join(leaf_nodes) if leaf_nodes else 'None'}")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python debug_connections.py <yaml_file>")
        sys.exit(1)
    
    yaml_file = Path(sys.argv[1])
    if not yaml_file.exists():
        print(f"Error: File '{yaml_file}' not found")
        sys.exit(1)
    
    debug_parse_yaml(yaml_file)