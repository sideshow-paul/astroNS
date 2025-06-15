#!/bin/bash
# Generate network diagrams using all three available tools
# This script demonstrates the different output formats and options

# Check if input YAML file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <yaml_file>"
    echo "Example: $0 network.yml"
    exit 1
fi

YAML_FILE="$1"
BASE_NAME=$(basename "$YAML_FILE" .yml)

# Check if YAML file exists
if [ ! -f "$YAML_FILE" ]; then
    echo "Error: File '$YAML_FILE' not found"
    exit 1
fi

echo "Generating network diagrams for: $YAML_FILE"
echo "============================================"

# Create output directory
OUTPUT_DIR="network_diagrams_${BASE_NAME}"
mkdir -p "$OUTPUT_DIR"

# 1. Generate SVG using yaml_network_diagram.py (Enhanced version)
echo -e "\n1. Generating enhanced SVG diagram..."
python yaml_network_diagram.py "$YAML_FILE" -o "$OUTPUT_DIR/${BASE_NAME}_enhanced.svg"
echo "   Output: $OUTPUT_DIR/${BASE_NAME}_enhanced.svg"

# 2. Generate SVG using yaml_to_network_svg.py (Basic version)
echo -e "\n2. Generating basic SVG diagram..."
python yaml_to_network_svg.py "$YAML_FILE" -o "$OUTPUT_DIR/${BASE_NAME}_basic.svg"
echo "   Output: $OUTPUT_DIR/${BASE_NAME}_basic.svg"

# 3. Generate Graphviz DOT with HTML-like labels
echo -e "\n3. Generating Graphviz DOT (HTML labels)..."
python yaml_to_graphviz.py "$YAML_FILE" -o "$OUTPUT_DIR/${BASE_NAME}_html.dot"
echo "   Output: $OUTPUT_DIR/${BASE_NAME}_html.dot"

# 4. Generate Graphviz DOT with simple labels
echo -e "\n4. Generating Graphviz DOT (simple labels)..."
python yaml_to_graphviz.py "$YAML_FILE" -o "$OUTPUT_DIR/${BASE_NAME}_simple.dot" --simple
echo "   Output: $OUTPUT_DIR/${BASE_NAME}_simple.dot"

# Check if Graphviz is installed
if command -v dot &> /dev/null; then
    echo -e "\n5. Converting Graphviz DOT files to images..."
    
    # Generate PNG from HTML-labeled DOT
    dot -Tpng "$OUTPUT_DIR/${BASE_NAME}_html.dot" -o "$OUTPUT_DIR/${BASE_NAME}_graphviz.png"
    echo "   Generated: $OUTPUT_DIR/${BASE_NAME}_graphviz.png"
    
    # Generate SVG from HTML-labeled DOT
    dot -Tsvg "$OUTPUT_DIR/${BASE_NAME}_html.dot" -o "$OUTPUT_DIR/${BASE_NAME}_graphviz.svg"
    echo "   Generated: $OUTPUT_DIR/${BASE_NAME}_graphviz.svg"
    
    # Generate PDF from HTML-labeled DOT
    dot -Tpdf "$OUTPUT_DIR/${BASE_NAME}_html.dot" -o "$OUTPUT_DIR/${BASE_NAME}_graphviz.pdf"
    echo "   Generated: $OUTPUT_DIR/${BASE_NAME}_graphviz.pdf"
    
    # Try different layout engines
    echo -e "\n6. Trying different Graphviz layout engines..."
    
    if command -v neato &> /dev/null; then
        neato -Tpng "$OUTPUT_DIR/${BASE_NAME}_html.dot" -o "$OUTPUT_DIR/${BASE_NAME}_neato.png"
        echo "   Generated: $OUTPUT_DIR/${BASE_NAME}_neato.png (spring model layout)"
    fi
    
    if command -v fdp &> /dev/null; then
        fdp -Tpng "$OUTPUT_DIR/${BASE_NAME}_html.dot" -o "$OUTPUT_DIR/${BASE_NAME}_fdp.png"
        echo "   Generated: $OUTPUT_DIR/${BASE_NAME}_fdp.png (force-directed layout)"
    fi
    
    if command -v sfdp &> /dev/null; then
        sfdp -Tpng "$OUTPUT_DIR/${BASE_NAME}_html.dot" -o "$OUTPUT_DIR/${BASE_NAME}_sfdp.png"
        echo "   Generated: $OUTPUT_DIR/${BASE_NAME}_sfdp.png (large graph layout)"
    fi
    
    if command -v circo &> /dev/null; then
        circo -Tpng "$OUTPUT_DIR/${BASE_NAME}_html.dot" -o "$OUTPUT_DIR/${BASE_NAME}_circo.png"
        echo "   Generated: $OUTPUT_DIR/${BASE_NAME}_circo.png (circular layout)"
    fi
else
    echo -e "\n[WARNING] Graphviz not installed. Install it to generate images from DOT files:"
    echo "  Ubuntu/Debian: sudo apt-get install graphviz"
    echo "  macOS: brew install graphviz"
    echo "  Windows: Download from https://graphviz.org/download/"
fi

echo -e "\n============================================"
echo "All diagrams have been generated in: $OUTPUT_DIR/"
echo ""
echo "File types generated:"
echo "  - Enhanced SVG (custom layout algorithm)"
echo "  - Basic SVG (simple layout)"
echo "  - Graphviz DOT files (can be edited/processed further)"
if command -v dot &> /dev/null; then
    echo "  - PNG, SVG, PDF from Graphviz"
    echo "  - Multiple layout variations (if available)"
fi

# Generate a comparison HTML file if we have all outputs
if command -v dot &> /dev/null; then
    cat > "$OUTPUT_DIR/comparison.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Network Diagram Comparison</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { display: flex; flex-wrap: wrap; gap: 20px; }
        .diagram { border: 1px solid #ccc; padding: 10px; }
        .diagram h3 { margin-top: 0; }
        img { max-width: 800px; height: auto; }
        .svg-container { max-width: 800px; overflow: auto; }
    </style>
</head>
<body>
    <h1>Network Diagram Comparison</h1>
    
    <h2>Custom SVG Layouts</h2>
    <div class="container">
        <div class="diagram">
            <h3>Enhanced SVG</h3>
            <div class="svg-container">
                <object data="BASE_NAME_enhanced.svg" type="image/svg+xml"></object>
            </div>
        </div>
        <div class="diagram">
            <h3>Basic SVG</h3>
            <div class="svg-container">
                <object data="BASE_NAME_basic.svg" type="image/svg+xml"></object>
            </div>
        </div>
    </div>
    
    <h2>Graphviz Layouts</h2>
    <div class="container">
        <div class="diagram">
            <h3>Dot (Hierarchical)</h3>
            <img src="BASE_NAME_graphviz.png" alt="Dot layout">
        </div>
        <div class="diagram">
            <h3>Neato (Spring Model)</h3>
            <img src="BASE_NAME_neato.png" alt="Neato layout">
        </div>
        <div class="diagram">
            <h3>FDP (Force-Directed)</h3>
            <img src="BASE_NAME_fdp.png" alt="FDP layout">
        </div>
        <div class="diagram">
            <h3>Circo (Circular)</h3>
            <img src="BASE_NAME_circo.png" alt="Circo layout">
        </div>
    </div>
</body>
</html>
EOF
    
    # Replace BASE_NAME with actual base name
    sed -i.bak "s/BASE_NAME/${BASE_NAME}/g" "$OUTPUT_DIR/comparison.html" && rm "$OUTPUT_DIR/comparison.html.bak"
    
    echo ""
    echo "Comparison HTML file generated: $OUTPUT_DIR/comparison.html"
    echo "Open this file in a web browser to compare all diagram types side by side."
fi