#!/usr/bin/env python3
"""
Generate network diagram SVG from YAML configuration files.

This script parses YAML files that define node networks and creates SVG visualizations
showing nodes with all their properties and connections between them.
"""

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml


class NetworkDiagramGenerator:
    """Generate SVG network diagrams from YAML configuration."""

    def __init__(self, width: int = 2000, height: int = 3000):
        """Initialize the generator with canvas dimensions."""
        self.width = width
        self.height = height
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.connections: List[Tuple[str, str, str]] = []  # (from, to, label)
        self.node_positions: Dict[str, Tuple[float, float]] = {}
        self.node_dimensions: Dict[str, Tuple[float, float]] = {}  # (width, height)
        self.colors = {
            'PulsarTopicSource': ('#e3f2fd', '#1976d2'),
            'PulsarTopicSink': ('#ffebee', '#c62828'),
            'ParseJsonMessage': ('#f3e5f5', '#7b1fa2'),
            'KeyDelayTime': ('#fff3e0', '#f57c00'),
            'RandomDistrib': ('#e8f5e9', '#388e3c'),
            'AddKeyValue': ('#fce4ec', '#c2185b'),
            'CalculateGeometry': ('#f1f8e9', '#689f38'),
            'CalculateGSD': ('#fff8e1', '#ffa000'),
            'DelayTime': ('#eceff1', '#37474f'),
            'default': ('#f5f5f5', '#666666')
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

    def calculate_layout(self) -> None:
        """Calculate node positions using a hierarchical layout algorithm."""
        if not self.nodes:
            return

        # First, calculate node dimensions
        for node_name in self.nodes:
            width, height = self._calculate_node_dimensions(node_name)
            self.node_dimensions[node_name] = (width, height)

        # Create layers based on dependencies
        layers = self._create_layers()

        # Position nodes
        y_start = 100
        current_y = y_start

        for layer_idx, layer_nodes in enumerate(layers):
            # Find the maximum height in this layer
            max_height_in_layer = max(self.node_dimensions[node][1] for node in layer_nodes)

            # Calculate total width needed for this layer with proper spacing
            total_width = sum(self.node_dimensions[node][0] for node in layer_nodes)
            min_spacing = 100  # Minimum spacing between nodes
            total_width += (len(layer_nodes) - 1) * min_spacing

            # If total width exceeds canvas, wrap to multiple rows
            if total_width > self.width - 100:
                # Arrange in multiple rows
                nodes_per_row = max(1, int((self.width - 100) / (max(self.node_dimensions[node][0] for node in layer_nodes) + min_spacing)))
                row_count = (len(layer_nodes) + nodes_per_row - 1) // nodes_per_row

                for row_idx in range(row_count):
                    row_nodes = layer_nodes[row_idx * nodes_per_row:(row_idx + 1) * nodes_per_row]
                    row_width = sum(self.node_dimensions[node][0] for node in row_nodes)
                    row_width += (len(row_nodes) - 1) * min_spacing

                    x_start = (self.width - row_width) / 2
                    current_x = x_start

                    for node in row_nodes:
                        node_width, node_height = self.node_dimensions[node]
                        x = current_x + node_width / 2
                        y = current_y + node_height / 2
                        self.node_positions[node] = (x, y)
                        current_x += node_width + min_spacing

                    if row_idx < row_count - 1:
                        current_y += max_height_in_layer + 80
            else:
                # Single row layout
                x_start = (self.width - total_width) / 2
                current_x = x_start

                for node in layer_nodes:
                    node_width, node_height = self.node_dimensions[node]
                    x = current_x + node_width / 2
                    y = current_y + node_height / 2
                    self.node_positions[node] = (x, y)
                    current_x += node_width + min_spacing

            # Move to next layer
            current_y += max_height_in_layer + 80

    def _calculate_node_dimensions(self, node_name: str) -> Tuple[float, float]:
        """Calculate width and height needed for a node based on its content."""
        node_data = self.nodes[node_name]

        # Calculate width based on longest text
        max_text_width = len(node_name) * 10  # Approximate character width

        for key, value in node_data.items():
            if key in self.nodes:  # Skip sub-node references
                continue

            # Format the key-value pair
            if isinstance(value, list):
                if len(value) <= 13 and all(isinstance(v, (str, int, float)) for v in value):
                    text = f"{key}: {value}"
                else:
                    text = f"{key}: [{len(value)} items]"
            elif isinstance(value, dict):
                text = f"{key}: {{{len(value)} items}}"
            elif value is None or value == '~':
                text = f"{key}: ~"
            else:
                text = f"{key}: {str(value)}"

            max_text_width = max(max_text_width, len(text) * 8)

        # Calculate height based on number of properties
        property_count = sum(1 for k in node_data.keys() if k not in self.nodes)
        height = 80 + property_count * 20  # Base height + line height per property (increased spacing)

        # Set minimum and maximum dimensions
        width = min(max(350, max_text_width + 60), 600)  # Increased minimum and maximum width
        height = max(100, height)  # Increased minimum height

        return width, height

    def _create_layers(self) -> List[List[str]]:
        """Create layers of nodes based on dependencies."""
        # Find incoming connections for each node
        incoming = {node: set() for node in self.nodes}

        for from_node, to_node, _ in self.connections:
            if to_node in incoming:
                incoming[to_node].add(from_node)

        # Topological sort with layers
        layers = []
        processed = set()

        # Find root nodes (no incoming connections)
        roots = [node for node in self.nodes if not incoming[node]]
        if roots:
            layers.append(roots)
            processed.update(roots)

        # Build subsequent layers
        while len(processed) < len(self.nodes):
            current_layer = []

            for node in self.nodes:
                if node not in processed:
                    # Check if all dependencies are processed
                    if all(dep in processed for dep in incoming[node]):
                        current_layer.append(node)

            if not current_layer:
                # Handle cycles or disconnected nodes
                for node in self.nodes:
                    if node not in processed:
                        current_layer.append(node)
                        break

            if current_layer:
                layers.append(current_layer)
                processed.update(current_layer)

        return layers

    def _escape_xml(self, text: str) -> str:
        """Escape special XML characters."""
        if not isinstance(text, str):
            text = str(text)
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&apos;'))

    def generate_svg(self) -> str:
        """Generate the SVG content."""
        svg_parts = []

        # Calculate actual height needed
        if self.node_positions:
            max_y = max(pos[1] for pos in self.node_positions.values())
            max_height = max(self.node_dimensions[node][1] for node in self.nodes)
            actual_height = max(self.height, max_y + max_height + 200)
        else:
            actual_height = self.height

        # SVG header
        svg_parts.append(f'<svg width="{self.width}" height="{actual_height}" xmlns="http://www.w3.org/2000/svg">')

        # Definitions
        svg_parts.append(self._generate_defs())

        # Title
        svg_parts.append(f'<text x="{self.width/2}" y="40" text-anchor="middle" '
                        'font-family="Arial, sans-serif" font-size="24" font-weight="bold" fill="#333">'
                        'Network Flow Diagram</text>')

        # Draw connections first (so they appear behind nodes)
        for from_node, to_node, label in self.connections:
            if from_node in self.node_positions and to_node in self.node_positions:
                svg_parts.append(self._draw_connection(from_node, to_node, label))

        # Draw nodes
        for node_name in self.nodes:
            if node_name in self.node_positions:
                svg_parts.append(self._draw_node(node_name))

        # Legend
        svg_parts.append(self._draw_legend(actual_height))

        # Close SVG
        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)

    def _generate_defs(self) -> str:
        """Generate SVG definitions for reusable elements."""
        return '''<defs>
    <!-- Arrow marker definition -->
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#333" />
    </marker>

    <!-- Drop shadow filter -->
    <filter id="dropshadow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="3"/>
      <feOffset dx="2" dy="2" result="offsetblur"/>
      <feComponentTransfer>
        <feFuncA type="linear" slope="0.3"/>
      </feComponentTransfer>
      <feMerge>
        <feMergeNode/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>'''

    def _draw_node(self, node_name: str) -> str:
        """Draw a single node with all its properties."""
        x, y = self.node_positions[node_name]
        width, height = self.node_dimensions[node_name]
        node_data = self.nodes[node_name]
        node_type = node_data.get('type', 'Unknown')

        # Get colors
        fill_color, stroke_color = self.colors.get(node_type, self.colors['default'])

        # Adjust position to center
        rect_x = x - width / 2
        rect_y = y - height / 2

        parts = []

        # Rectangle
        parts.append(f'<rect x="{rect_x}" y="{rect_y}" width="{width}" height="{height}" '
                    f'rx="10" fill="{fill_color}" stroke="{stroke_color}" stroke-width="2" '
                    'filter="url(#dropshadow)"/>')

        # Node name
        text_y = rect_y + 30
        parts.append(f'<text x="{x}" y="{text_y}" text-anchor="middle" '
                    'font-family="Arial, sans-serif" font-size="16" font-weight="bold" '
                    f'fill="{stroke_color}">{self._escape_xml(node_name)}</text>')

        # Add horizontal line after name
        line_y = text_y + 10
        parts.append(f'<line x1="{rect_x + 20}" y1="{line_y}" x2="{rect_x + width - 20}" y2="{line_y}" '
                    'stroke="#ddd" stroke-width="1"/>')

        # Node properties
        text_y = line_y + 20
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
            max_chars = int((width - 80) / 7)  # Approximate character width (adjusted for better fit)
            if len(value_str) > max_chars:
                value_str = value_str[:max_chars-3] + "..."

            parts.append(f'<text x="{rect_x + 15}" y="{text_y}" '
                        'font-family="Arial, sans-serif" font-size="12" fill="#555">'
                        f'{self._escape_xml(key)}: {self._escape_xml(value_str)}</text>')

            text_y += 20  # Increased line spacing

        return '\n'.join(parts)

    def _draw_connection(self, from_node: str, to_node: str, label: str) -> str:
        """Draw a connection between two nodes."""
        x1, y1 = self.node_positions[from_node]
        x2, y2 = self.node_positions[to_node]

        # Get node dimensions
        from_width, from_height = self.node_dimensions[from_node]
        to_width, to_height = self.node_dimensions[to_node]

        parts = []

        # Determine connection points based on relative positions
        if y2 > y1:  # Forward connection (going down)
            # Connect from bottom of source to top of target
            y1_adj = y1 + from_height / 2
            y2_adj = y2 - to_height / 2

            if abs(x2 - x1) < 50:  # Nearly vertical
                parts.append(f'<line x1="{x1}" y1="{y1_adj}" x2="{x2}" y2="{y2_adj}" '
                            'stroke="#333" stroke-width="2" marker-end="url(#arrowhead)"/>')
                label_x = x1 + 20
                label_y = (y1_adj + y2_adj) / 2
            else:  # Curved connection
                cx = (x1 + x2) / 2
                cy = (y1_adj + y2_adj) / 2
                parts.append(f'<path d="M {x1} {y1_adj} Q {cx} {cy} {x2} {y2_adj}" '
                            'fill="none" stroke="#333" stroke-width="2" marker-end="url(#arrowhead)"/>')
                label_x = cx
                label_y = cy

        elif y2 < y1:  # Backward connection (going up)
            # Connect from left/right side back up
            y1_adj = y1
            y2_adj = y2

            # Determine which side to use based on relative positions
            if x1 < self.width / 2:
                # Use left side
                x1_adj = x1 - from_width / 2
                x2_adj = x2 - to_width / 2
                side_offset = -200
            else:
                # Use right side
                x1_adj = x1 + from_width / 2
                x2_adj = x2 + to_width / 2
                side_offset = 200

            cx = (x1_adj + x2_adj) / 2 + side_offset
            parts.append(f'<path d="M {x1_adj} {y1_adj} Q {cx} {(y1_adj + y2_adj) / 2} {x2_adj} {y2_adj}" '
                        'fill="none" stroke="#333" stroke-width="2" marker-end="url(#arrowhead)"/>')
            label_x = cx
            label_y = (y1_adj + y2_adj) / 2

        else:  # Same level (y1 == y2)
            # Horizontal connection
            if x1 < x2:
                x1_adj = x1 + from_width / 2
                x2_adj = x2 - to_width / 2
            else:
                x1_adj = x1 - from_width / 2
                x2_adj = x2 + to_width / 2

            parts.append(f'<line x1="{x1_adj}" y1="{y1}" x2="{x2_adj}" y2="{y2}" '
                        'stroke="#333" stroke-width="2" marker-end="url(#arrowhead)"/>')
            label_x = (x1_adj + x2_adj) / 2
            label_y = y1 - 20

        # Draw label only if it's not empty
        if label:
            if ':' in label and len(label) > 40:
                # Split long conditional labels
                parts_label = label.split(':', 1)
                parts.append(f'<text x="{label_x}" y="{label_y - 8}" text-anchor="middle" '
                            'font-family="Arial, sans-serif" font-size="13" fill="#666">'
                            f'{self._escape_xml(parts_label[0] + ":")}</text>')
                parts.append(f'<text x="{label_x}" y="{label_y + 8}" text-anchor="middle" '
                            'font-family="Arial, sans-serif" font-size="12" fill="#888">'
                            f'{self._escape_xml(parts_label[1].strip())}</text>')
            else:
                parts.append(f'<text x="{label_x}" y="{label_y}" text-anchor="middle" '
                            'font-family="Arial, sans-serif" font-size="13" fill="#666">'
                            f'{self._escape_xml(label)}</text>')

        return '\n'.join(parts)

    def _draw_legend(self, height: float) -> str:
        """Draw a legend explaining the notation."""
        x = 50
        y = height - 150

        return f'''<rect x="{x}" y="{y}" width="250" height="120" rx="5" fill="#f5f5f5" stroke="#999" stroke-width="1"/>
  <text x="{x + 125}" y="{y + 25}" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#333">Legend</text>
  <text x="{x + 10}" y="{y + 45}" font-family="Arial, sans-serif" font-size="12" fill="#555">Node box = YAML section</text>
  <text x="{x + 10}" y="{y + 65}" font-family="Arial, sans-serif" font-size="12" fill="#555">Properties = key: value pairs</text>
  <text x="{x + 10}" y="{y + 85}" font-family="Arial, sans-serif" font-size="12" fill="#555">Arrow = sub-key reference</text>
  <text x="{x + 10}" y="{y + 105}" font-family="Arial, sans-serif" font-size="12" fill="#555">~ = Empty/null value</text>'''


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate network diagram SVG from YAML configuration file'
    )
    parser.add_argument('yaml_file', type=Path, help='Path to YAML configuration file')
    parser.add_argument('-o', '--output', type=Path, help='Output SVG file path')
    parser.add_argument('-w', '--width', type=int, default=2000, help='SVG width (default: 2000)')
    parser.add_argument('--height', type=int, default=3000, help='SVG height (default: 3000)')

    args = parser.parse_args()

    # Read YAML file
    try:
        with open(args.yaml_file, 'r') as f:
            yaml_content = yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading YAML file: {e}", file=sys.stderr)
        return 1

    # Generate diagram
    generator = NetworkDiagramGenerator(width=args.width, height=args.height)
    generator.parse_yaml(yaml_content)
    generator.calculate_layout()
    svg_content = generator.generate_svg()

    # Write output
    output_path = args.output
    if not output_path:
        # Default output name based on input
        output_path = args.yaml_file.with_suffix('.svg')

    try:
        with open(output_path, 'w') as f:
            f.write(svg_content)
        print(f"Generated network diagram: {output_path}")
    except Exception as e:
        print(f"Error writing SVG file: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
