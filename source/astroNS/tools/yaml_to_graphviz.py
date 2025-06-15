#!/usr/bin/env python3
"""
Convert YAML network configuration files to Graphviz DOT format.

This script parses YAML files that define node networks and creates Graphviz DOT files
showing nodes with all their properties and connections between them.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


class YamlToGraphvizConverter:
    """Convert YAML network configurations to Graphviz DOT format."""

    def __init__(self):
        """Initialize the converter."""
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.connections: List[Tuple[str, str, str]] = []  # (from, to, label)
        self.node_colors = {
            'PulsarTopicSource': '#e3f2fd',
            'PulsarTopicSink': '#ffebee',
            'ParseJsonMessage': '#f3e5f5',
            'KeyDelayTime': '#fff3e0',
            'RandomDistrib': '#e8f5e9',
            'AddKeyValue': '#fce4ec',
            'CalculateGeometry': '#f1f8e9',
            'CalculateGSD': '#fff8e1',
            'DelayTime': '#eceff1',
            'default': '#f5f5f5'
        }
        self.edge_colors = {
            'PulsarTopicSource': '#1976d2',
            'PulsarTopicSink': '#c62828',
            'ParseJsonMessage': '#7b1fa2',
            'KeyDelayTime': '#f57c00',
            'RandomDistrib': '#388e3c',
            'AddKeyValue': '#c2185b',
            'CalculateGeometry': '#689f38',
            'CalculateGSD': '#ffa000',
            'DelayTime': '#37474f',
            'default': '#666666'
        }

    def parse_yaml(self, yaml_content: Dict[str, Any]) -> None:
        """Parse YAML content and extract nodes and connections."""
        # First, collect all node names (excluding DEFAULT)
        all_node_names = set(key for key in yaml_content.keys() if key != 'DEFAULT')

        # Parse nodes and their connections
        for node_name, node_config in yaml_content.items():
            if node_name == 'DEFAULT':
                continue

            if isinstance(node_config, dict):
                self.nodes[node_name] = node_config.copy()

                # Find connections - any sub-key that matches a node name is a connection
                for key, value in node_config.items():
                    if key in all_node_names:
                        # This key is a node name, so it's a connection
                        if value is None:
                            label = ""  # No label for ~ values
                        elif isinstance(value, str):
                            # Check if it's just a tilde or empty
                            if value.strip() in ['~', '']:
                                label = ""  # No label for ~ values
                            else:
                                # It has a condition or value
                                label = f"{key}: {value}"
                        else:
                            # Non-string value (could be bool, number, etc.)
                            label = f"{key}: {value}"

                        self.connections.append((node_name, key, label))

    def _escape_graphviz(self, text: str) -> str:
        """Escape special characters for Graphviz."""
        if not isinstance(text, str):
            text = str(text)
        # Escape quotes and backslashes
        text = text.replace('\\', '\\\\')
        text = text.replace('"', '\\"')
        text = text.replace('<', '\\<')
        text = text.replace('>', '\\>')
        text = text.replace('{', '\\{')
        text = text.replace('}', '\\}')
        text = text.replace('|', '\\|')
        return text

    def _format_node_label(self, node_name: str) -> str:
        """Format node label with all properties in HTML-like format."""
        node_data = self.nodes[node_name]
        node_type = node_data.get('type', 'Unknown')

        # Get colors
        fill_color = self.node_colors.get(node_type, self.node_colors['default'])
        edge_color = self.edge_colors.get(node_type, self.edge_colors['default'])

        # Start building the label
        label_parts = []
        label_parts.append('<<TABLE BORDER="2" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6"')
        label_parts.append(f' BGCOLOR="{fill_color}" COLOR="{edge_color}" STYLE="ROUNDED">')

        # Node name header
        label_parts.append('<TR><TD COLSPAN="2" ALIGN="CENTER">')
        label_parts.append(f'<FONT POINT-SIZE="16" COLOR="{edge_color}"><B>')
        label_parts.append(self._escape_graphviz(node_name))
        label_parts.append('</B></FONT></TD></TR>')

        # Separator - use a cell with background color instead of HR
        label_parts.append('<TR><TD COLSPAN="2" HEIGHT="1" BGCOLOR="#dddddd"></TD></TR>')

        # Node properties
        for key, value in sorted(node_data.items()):
            # Skip sub-nodes in property display
            if key in self.nodes:
                continue

            # Format value
            if isinstance(value, list):
                if len(value) <= 13 and all(isinstance(v, (str, int, float)) for v in value):
                    value_str = str(value)
                else:
                    value_str = f"[{len(value)} items]"
            elif isinstance(value, dict):
                value_str = f"{{{len(value)} items}}"
            elif value is None or value == '~':
                value_str = "~"
            elif isinstance(value, bool):
                value_str = str(value).lower()
            else:
                value_str = str(value)

            # Truncate long values
            if len(value_str) > 50:
                value_str = value_str[:47] + "..."

            label_parts.append('<TR>')
            label_parts.append(f'<TD ALIGN="LEFT" BALIGN="LEFT"><FONT POINT-SIZE="11" COLOR="#333333">{self._escape_graphviz(key)}:</FONT></TD>')
            label_parts.append(f'<TD ALIGN="LEFT" BALIGN="LEFT"><FONT POINT-SIZE="11" COLOR="#666666">{self._escape_graphviz(value_str)}</FONT></TD>')
            label_parts.append('</TR>')

        label_parts.append('</TABLE>>')

        return ''.join(label_parts)

    def generate_dot(self) -> str:
        """Generate the Graphviz DOT content."""
        dot_parts = []

        # DOT header
        dot_parts.append('digraph NetworkFlow {')
        dot_parts.append('    // Graph settings')
        dot_parts.append('    rankdir=TB;')
        dot_parts.append('    node [shape=none, fontname="Arial", margin=0];')
        dot_parts.append('    edge [fontname="Arial", fontsize=12, fontcolor="#444444"];')
        dot_parts.append('    bgcolor="white";')
        dot_parts.append('    pad=0.5;')
        dot_parts.append('    nodesep=0.5;')
        dot_parts.append('    ranksep=1.0;')
        dot_parts.append('')

        # Add title
        dot_parts.append('    // Title')
        dot_parts.append('    labelloc="t";')
        dot_parts.append('    label="Network Flow Diagram";')
        dot_parts.append('    fontsize=24;')
        dot_parts.append('    fontname="Arial";')
        dot_parts.append('')

        # Define nodes
        dot_parts.append('    // Nodes')
        for node_name in sorted(self.nodes.keys()):
            label = self._format_node_label(node_name)
            # Make node names safe for Graphviz
            safe_name = f'"{node_name}"'
            dot_parts.append(f'    {safe_name} [label={label}];')

        dot_parts.append('')

        # Define edges
        dot_parts.append('    // Connections')
        for from_node, to_node, label in self.connections:
            safe_from = f'"{from_node}"'
            safe_to = f'"{to_node}"'

            if label:
                # Connection with label
                escaped_label = self._escape_graphviz(label)
                dot_parts.append(f'    {safe_from} -> {safe_to} [label="{escaped_label}", labeldistance=2];')
            else:
                # Connection without label (for ~ values)
                dot_parts.append(f'    {safe_from} -> {safe_to};')

        dot_parts.append('}')

        return '\n'.join(dot_parts)

    def generate_dot_simple(self) -> str:
        """Generate a simpler DOT format without HTML labels."""
        dot_parts = []

        # DOT header
        dot_parts.append('digraph NetworkFlow {')
        dot_parts.append('    // Graph settings')
        dot_parts.append('    rankdir=TB;')
        dot_parts.append('    node [shape=record, style=filled, fontname="Arial"];')
        dot_parts.append('    edge [fontname="Arial", fontsize=12];')
        dot_parts.append('    bgcolor="white";')
        dot_parts.append('')

        # Define nodes with simple labels
        dot_parts.append('    // Nodes')
        for node_name in sorted(self.nodes.keys()):
            node_data = self.nodes[node_name]
            node_type = node_data.get('type', 'Unknown')

            # Get colors
            fill_color = self.node_colors.get(node_type, self.node_colors['default'])

            # Build simple label
            label_parts = [node_name]
            label_parts.append('\\n━━━━━━━━━━━━━━━━')

            for key, value in sorted(node_data.items()):
                # Skip sub-nodes
                if key in self.nodes:
                    continue

                # Format value
                if isinstance(value, list):
                    if len(value) <= 13 and all(isinstance(v, (str, int, float)) for v in value):
                        value_str = str(value)
                    else:
                        value_str = f"[{len(value)} items]"
                elif isinstance(value, dict):
                    value_str = f"{{{len(value)} items}}"
                elif value is None or value == '~':
                    value_str = "~"
                elif isinstance(value, bool):
                    value_str = str(value).lower()
                else:
                    value_str = str(value)

                # Truncate long values
                if len(value_str) > 40:
                    value_str = value_str[:37] + "..."

                label_parts.append(f"\\n{key}: {value_str}")

            label = ''.join(label_parts)
            escaped_label = self._escape_graphviz(label)
            safe_name = f'"{node_name}"'

            dot_parts.append(f'    {safe_name} [label="{escaped_label}", fillcolor="{fill_color}"];')

        dot_parts.append('')

        # Define edges
        dot_parts.append('    // Connections')
        for from_node, to_node, label in self.connections:
            safe_from = f'"{from_node}"'
            safe_to = f'"{to_node}"'

            if label:
                escaped_label = self._escape_graphviz(label)
                dot_parts.append(f'    {safe_from} -> {safe_to} [label="{escaped_label}"];')
            else:
                dot_parts.append(f'    {safe_from} -> {safe_to};')

        dot_parts.append('}')

        return '\n'.join(dot_parts)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Convert YAML network configuration to Graphviz DOT format'
    )
    parser.add_argument('yaml_file', type=Path, help='Path to YAML configuration file')
    parser.add_argument('-o', '--output', type=Path, help='Output DOT file path')
    parser.add_argument('-s', '--simple', action='store_true',
                       help='Use simple format instead of HTML-like labels')

    args = parser.parse_args()

    # Read YAML file
    try:
        with open(args.yaml_file, 'r') as f:
            yaml_content = yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading YAML file: {e}", file=sys.stderr)
        return 1

    # Generate DOT
    converter = YamlToGraphvizConverter()
    converter.parse_yaml(yaml_content)

    if args.simple:
        dot_content = converter.generate_dot_simple()
    else:
        dot_content = converter.generate_dot()

    # Write output
    output_path = args.output
    if not output_path:
        # Default output name based on input
        output_path = args.yaml_file.with_suffix('.dot')

    try:
        with open(output_path, 'w') as f:
            f.write(dot_content)
        print(f"Generated Graphviz DOT file: {output_path}")
        print(f"To create an image, run: dot -Tpng {output_path} -o {output_path.with_suffix('.png')}")
    except Exception as e:
        print(f"Error writing DOT file: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
