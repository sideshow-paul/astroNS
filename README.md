# astroNS

**astroNS** is a Python library for advanced astrophysical calculations, network modeling, and simulation of satellite data streams. It provides a modular node‑based architecture for building complex simulation pipelines, utilities for parsing and validating data with Pydantic, and a Streamlit UI for visualizing results.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Core Modules](#core-modules)
- [Command‑Line Tools](#command-line-tools)
- [Testing](#testing)
- [Development Workflow](#development-workflow)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

astroNS is built around a **node graph** where each node inherits from `BaseNode`. Nodes can be sources, processors, or sinks, and communicate via typed messages (Pydantic models). The library ships with:

- Pulsar message sources/sinks with optional Pydantic validation
- Aerospace utilities for geometry, ground‑sample‑distance (GSD) and satellite lookup
- A flexible argument parser that can be reused across entry points
- Streamlit UI (`applications/streamlit`) for interactive exploration of simulation results
- Helper scripts for converting YAML network definitions to Graphviz diagrams

---

## Features

- **Modular node architecture** – compose pipelines from reusable components.
- **Typed messages** – Pydantic models guarantee schema validation and auto‑documentation.
- **Simulation engine** – thin wrapper around `simpy` for time‑driven simulations.
- **Pulsar integration** – publish/subscribe to Apache Pulsar topics with optional schema enforcement.
- **Streamlit dashboards** – real‑time visualisation of satellite tracks and geometry.
- **CLI utilities** – manage satellites, generate network diagrams, and run simulations.
- **Comprehensive test suite** – unit and integration tests under `tests/`.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/yourorg/astroNS.git
cd astroNS

# Install in editable mode with development dependencies
python -m pip install -e .[dev]
```

The `pyproject.toml` and `requirements.txt` pin exact dependency versions. For a minimal runtime install omit the `[dev]` extra.

---

## Quick Start

```python
from astroNS.core import NetworkModel

# Initialise the simulation environment
model = NetworkModel()

# Run the simulation for 10 simulated seconds
result = model.run(duration=10)

print("Simulation completed:")
print(result)
```

For a full example see `source/astroNS/nodes/aerospace/calculate_geometry.py` and the accompanying test `test_calculate_geometry_keys.py`.

---

## Architecture

```
+-------------------+      +-------------------+      +-------------------+
|  Message Source   | -->  |   Processor Node  | -->  |   Message Sink    |
+-------------------+      +-------------------+      +-------------------+
        ^                         ^                         ^
        |                         |                         |
   PulsarTopicSource      CalculateGeometry          PulsarTopicSink
```

- **BaseNode (`source/astroNS/nodes/core/base.py`)** – common functionality: logging, configuration handling, and lifecycle hooks.
- **Message Sources** – generate messages (e.g., `PulsarTopicSource`, `FileDataSource`).
- **Processors** – transform or enrich data (`CalculateGeometry`, `ParseJsonMessage`).
- **Message Sinks** – consume messages, optionally persisting or publishing (`PulsarTopicSink`).
- **Pydantic Models** – defined in `source/astroNS/nodes/pydantic_models/two_six_messages.py` and used throughout the pipeline.

---

## Core Modules

| Package | Description |
|---------|-------------|
| `astroNS.core` | High‑level `NetworkModel` class that wires nodes together and runs the SimPy environment. |
| `astroNS.nodes` | Node implementations grouped by domain (`aerospace`, `AI`, `core`). |
| `astroNS.tools` | Utility scripts: YAML → Graphviz, network diagram generation, etc. |
| `astroNS.data` | CLI helpers for adding/removing satellite definitions. |
| `applications/streamlit` | Streamlit UI entry point (`bobcat_ui.py`). |

---

## Command‑Line Tools

| Script | Purpose |
|--------|---------|
| `clear_pulsar_topic.py` | Purge messages from a Pulsar topic. |
| `parser.py` | Argument parsing utilities used by many entry points. |
| `network.dot` | Example Graphviz definition of a node network. |
| `pulsar_listener.py` | Simple Pulsar consumer for debugging. |
| `test_send_task_assignments.py` | Generates synthetic task assignment messages. |

Run any script with `-h`/`--help` for usage details.

---

## Testing

The project uses **pytest** with optional coverage reporting.

```bash
# Run the full test suite
pytest

# Run a single test file or function
pytest tests/unit/test_parser.py::test_argument_parsing -vv

# Coverage report
pytest --cov=. --cov-report=term-missing
```

All tests are located under the `tests/` directory and are grouped into unit and integration suites.

---

## Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/awesome-feature
   ```
2. **Make changes** – follow the code‑style guidelines in `AGENTS.md` (Black, Ruff, MyPy).
3. **Run lint and type‑check**
   ```bash
   ruff . && black --check . && mypy --strict .
   ```
4. **Run tests**
   ```bash
   pytest -n auto
   ```
5. **Commit** with conventional commit message format (`feat`, `fix`, etc.).
6. **Open a Pull Request** – CI will run the lint, type‑check, and test steps automatically.

---

## Contributing

Contributions are welcome! Please:

- Fork the repository and create a feature branch.
- Ensure code follows the style rules in `AGENTS.md`.
- Add or update tests for new functionality.
- Run the full CI locally before pushing.

See `CONTRIBUTING.md` (if present) for detailed guidelines.

---

## License

`astroNS` is released under the MIT License. See the `LICENSE` file for full terms.

---

## Contact

For questions or support, open an issue on the GitHub repository or contact the maintainer at `paulgreene@example.com`.
