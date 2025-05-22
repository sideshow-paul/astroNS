# MathisThroughputDelay - TCP Network Throughput Simulation Node

## Overview

The `MathisThroughputDelay` node implements a realistic TCP network delay model based on the Mathis equation. This model calculates network throughput and resulting transmission delays by considering:

- Maximum Segment Size (MSS)
- Round-Trip Time (RTT)
- Packet Loss Rate
- TCP Implementation Constant (C)

Unlike simpler bandwidth-based delay models, this implementation accounts for how TCP performance degrades with increased latency and packet loss, providing a more realistic simulation of real-world network conditions.

## The Mathis Equation

The Mathis equation models the maximum TCP throughput as:

```
Throughput ≤ (MSS * C) / (RTT * sqrt(p))
```

Where:
- MSS = Maximum Segment Size in bytes (typically 1460 bytes for Ethernet)
- RTT = Round Trip Time in seconds
- p = Packet loss probability as a decimal (e.g., 0.001 for 0.1%)
- C = Constant (typically 0.93 for TCP Reno)

## Usage

### Configuration Parameters

The node accepts the following configuration parameters:

| Parameter | Description | Default Value |
|-----------|-------------|---------------|
| `mss` | Maximum Segment Size in bytes | 1460.0 |
| `rtt` | Round Trip Time in seconds | 0.1 (100ms) |
| `packet_loss` | Packet loss probability (0-1) | 0.001 (0.1%) |
| `c_constant` | TCP implementation constant | 0.93 |

### Example Configuration

```python
mathis_config = {
    "mss": 1460.0,        # MSS in bytes (typical for Ethernet)
    "rtt": 0.1,           # RTT in seconds (100ms)
    "packet_loss": 0.001, # Packet loss rate of 0.1%
    "c_constant": 0.93    # Constant for TCP Reno
}
mathis_delay = MathisThroughputDelay(env, "MathisDelay", mathis_config)
```

## Integration with Simulation Framework

The node integrates seamlessly with the AstroNS simulation framework:

1. It extends the `BaseNode` class
2. It calculates delays based on message size and network parameters
3. It updates simulation timing appropriately
4. It provides detailed logging of network parameters and calculated throughput

## Example

See `astroNS/source/astroNS/examples/mathis_delay_example.py` for a complete example demonstrating how to use this node in a simulation with various network conditions.

## Comparison with DelaySize Node

Unlike the simpler `DelaySize` node that uses a fixed rate parameter, `MathisThroughputDelay` provides:

- More realistic modeling of TCP behavior
- Consideration of both latency and packet loss effects
- Automatic adaptation to changing network conditions during simulation
- Better simulation of high-latency or lossy networks (satellite links, congested networks, etc.)

## References

- Mathis, M., Semke, J., Mahdavi, J., & Ott, T. (1997). The macroscopic behavior of the TCP congestion avoidance algorithm. ACM SIGCOMM Computer Communication Review, 27(3), 67-82.