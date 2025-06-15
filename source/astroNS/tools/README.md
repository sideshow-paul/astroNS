# Network Diagram Generator for YAML Configurations

This directory contains Python scripts for generating network diagrams from YAML configuration files. These tools are particularly useful for visualizing complex node-based processing pipelines.

## Scripts

### 1. `yaml_network_diagram.py` (Recommended)
The enhanced version with improved layout algorithms and features for SVG output.

**Features:**
- Dynamic node sizing based on content
- Hierarchical layout with automatic layer detection
- Multi-row support for layers with many nodes
- Better connection routing (forward, backward, and lateral)
- All node properties displayed with proper formatting
- Prevents node overlap with intelligent spacing

### 2. `yaml_to_network_svg.py`
The basic version with simpler layout algorithms for SVG output.

**Features:**
- Basic node visualization
- Simple connection routing
- Fixed node sizes
- Basic property display

### 3. `yaml_to_graphviz.py`
Converts YAML networks to Graphviz DOT format for advanced layout algorithms.

**Features:**
- Generates Graphviz DOT files
- HTML-like labels with formatted tables
- Color-coded node types (same as SVG versions)
- All node properties displayed
- Conditional connection labels
- Simple format option for compatibility
- Can leverage Graphviz's powerful layout engines

## Installation

Requires Python 3.6+ and PyYAML:

```bash
pip install pyyaml
```

For Graphviz output, you'll also need Graphviz installed:

```bash
# Ubuntu/Debian
sudo apt-get install graphviz

# macOS
brew install graphviz

# Windows
# Download from https://graphviz.org/download/
```

## Usage

### Basic Usage

```bash
python yaml_network_diagram.py input.yml
```

This will create an SVG file with the same name as the input file (e.g., `input.svg`).

### Specify Output File

```bash
python yaml_network_diagram.py input.yml -o output.svg
```

### Custom Dimensions

```bash
python yaml_network_diagram.py input.yml --width 2400 --height 3600
```

### Graphviz Output

Generate a DOT file:

```bash
python yaml_to_graphviz.py input.yml -o output.dot
```

Generate a DOT file with simple labels:

```bash
python yaml_to_graphviz.py input.yml -o output.dot --simple
```

Convert DOT to image:

```bash
dot -Tpng output.dot -o output.png    # PNG format
dot -Tsvg output.dot -o output.svg    # SVG format
dot -Tpdf output.dot -o output.pdf    # PDF format
```

Use different layout engines:

```bash
neato -Tpng output.dot -o output.png  # Spring model layout
circo -Tpng output.dot -o output.png  # Circular layout
fdp -Tpng output.dot -o output.png    # Force-directed layout
```

## YAML File Format

The scripts expect YAML files with the following structure:

```yaml
# Optional DEFAULT section (ignored by diagram generator)
DEFAULT:
  key: value

# Node definitions
NodeName1:
  type: NodeType
  property1: value1
  property2: value2
  NextNode: ~  # Connection to NextNode

NodeName2:
  type: AnotherType
  ConditionalNext: condition == value  # Conditional connection
  
NextNode:
  type: FinalType
  # ... properties
```

### Connection Types

1. **Direct Connection**: `NextNode: ~`
   - Creates a connection to `NextNode` with no label (cleaner appearance)

2. **Conditional Connection**: `NextNode: condition == value`
   - Creates a connection with the condition displayed as label

3. **Value Connection**: `NextNode: some_value`
   - Creates a connection with the value displayed as label

## Visual Elements

### Nodes
- **Box**: Each YAML section becomes a node box
- **Title**: Node name displayed in bold at the top
- **Properties**: All key-value pairs listed below the title
- **Color**: Different node types have different colors based on the `type` field

### Connections
- **Arrows**: Show flow direction between nodes
- **Labels**: Display conditions or values (connections with `~` values have no labels for cleaner diagrams)
- **Routing**: Automatic routing to avoid overlaps
  - Forward connections: straight or curved down
  - Backward connections: curved around the side
  - Lateral connections: horizontal

### Layout
- **Hierarchical**: Nodes arranged in layers based on dependencies
- **Automatic spacing**: Prevents overlaps
- **Multi-row support**: Wide layers wrap to multiple rows
- **Dynamic sizing**: Node boxes sized to fit content

## Color Scheme

Default colors by node type:
- `PulsarTopicSource`: Blue (#e3f2fd, #1976d2)
- `PulsarTopicSink`: Red (#ffebee, #c62828)
- `ParseJsonMessage`: Purple (#f3e5f5, #7b1fa2)
- `KeyDelayTime`: Orange (#fff3e0, #f57c00)
- `RandomDistrib`: Green (#e8f5e9, #388e3c)
- `AddKeyValue`: Pink (#fce4ec, #c2185b)
- `CalculateGeometry`: Light Green (#f1f8e9, #689f38)
- `CalculateGSD`: Amber (#fff8e1, #ffa000)
- `DelayTime`: Grey (#eceff1, #37474f)
- Default: Light Grey (#f5f5f5, #666666)

## Examples

### Basic Example

Given a YAML file `pipeline.yml`:

```yaml
Source:
  type: FileReader
  path: /data/input.csv
  Process: ~

Process:
  type: DataProcessor
  algorithm: transform
  Output: ~
  ErrorHandler: status == "error"

Output:
  type: FileWriter
  path: /data/output.csv

ErrorHandler:
  type: Logger
  level: ERROR
```

Generate the diagram:

```bash
python yaml_network_diagram.py pipeline.yml -o pipeline_diagram.svg
```

This creates an SVG showing:
- Four nodes (Source, Process, Output, ErrorHandler)
- Connections showing the flow
- Conditional connection to ErrorHandler

### Graphviz Example

Generate multiple formats:

```bash
# Generate DOT file
python yaml_to_graphviz.py pipeline.yml

# Create high-quality PNG
dot -Tpng -Gdpi=300 pipeline.dot -o pipeline_hq.png

# Create PDF for documentation
dot -Tpdf pipeline.dot -o pipeline.pdf

# Use different layout for complex networks
neato -Tsvg pipeline.dot -o pipeline_neato.svg
```

## Tips

1. **Large Networks**: 
   - For SVG: Use larger dimensions
     ```bash
     python yaml_network_diagram.py complex.yml --width 3000 --height 4000
     ```
   - For Graphviz: Use appropriate layout engines
     ```bash
     python yaml_to_graphviz.py complex.yml -o complex.dot
     sfdp -Tpng complex.dot -o complex.png  # Good for large graphs
     ```

2. **Property Display**: Long property values are truncated with "..."
   - Lists show item count: `[5 items]`
   - Dicts show item count: `{3 items}`
   - Small lists (≤3 items) show full content

3. **Connection Labels**: 
   - Connections with `~` values have no labels for cleaner diagrams
   - Use `~` for simple connections where the arrow itself is sufficient
   - Use conditions or values when you need to show routing logic

4. **Complex Conditions**: Multi-line conditions are split for readability

## Troubleshooting

### Overlapping Nodes
- For SVG: Increase canvas width: `--width 3000`
- The script automatically wraps wide layers to multiple rows
- For Graphviz: Use different layout engines (neato, fdp, sfdp)

### Missing Connections
- Ensure target node names match exactly
- Check for typos in node references

### Large Files
- For very large networks, consider breaking into sub-networks
- Increase dimensions to accommodate all nodes

## Output Formats

### SVG Output (yaml_network_diagram.py, yaml_to_network_svg.py)
- Viewed in any web browser
- Edited in vector graphics software (Illustrator, Inkscape)
- Converted to other formats using ImageMagick
- Embedded directly in documentation

### Graphviz Output (yaml_to_graphviz.py)
- DOT files are text-based and version-control friendly
- Can generate multiple formats: PNG, SVG, PDF, PS
- Supports various layout algorithms
- Better for very large or complex networks
- Can be styled with Graphviz attributes

## Contributing

To extend the color scheme or modify layout algorithms, edit the respective script:
- Colors: Modify the `self.colors` dictionary in `__init__` (same in all scripts)
- SVG Layout: Modify `calculate_layout()` and `_create_layers()` methods
- Graphviz: Modify `generate_dot()` for DOT output customization

### Adding New Node Types

Add color mappings in all three scripts:
```python
self.node_colors = {
    'YourNodeType': '#hexcolor',
    # ... existing types
}
```