# Mathis Throughput Delay Model Example

## Overview

This example demonstrates how to use the `MathisThroughputDelay` node in an AstroNS simulation using YAML configuration. The model simulates different network conditions and shows how TCP throughput and transfer delays are affected by changes in Round Trip Time (RTT) and packet loss rates.

## The Mathis Equation

The simulation uses the Mathis equation to model TCP throughput:

```
Throughput ≤ (MSS * C) / (RTT * sqrt(p))
```

Where:
- MSS = Maximum Segment Size in bytes (typically 1460 bytes for Ethernet)
- RTT = Round Trip Time in seconds
- p = Packet loss probability as a decimal
- C = Constant (typically 0.93 for TCP Reno)

## Model Structure

The model consists of:

1. A message source that generates random-sized messages (1KB to 10MB)
2. Four different network scenarios, each implemented with a `MathisThroughputDelay` node:
   - Low latency (20ms), low loss (0.01%)
   - High latency (200ms), low loss (0.01%) 
   - Low latency (20ms), high loss (1%)
   - High latency (200ms), high loss (1%)
3. Sink nodes that display the results for each scenario

## Running the Example

To run this example:

```bash
python -m astroNS.astroNS -m MathisThroughputExample/MathisThroughputModel.yml
```

## Expected Results

The example will show:
- How throughput decreases as RTT increases
- How throughput decreases as packet loss increases
- How the same file size takes dramatically different times to transfer under different network conditions

## Real-world Applications

This model can be used to simulate various network conditions such as:
- Satellite links (high latency)
- Congested networks (high packet loss)
- Mobile networks (variable conditions)
- Cross-continental connections (high latency)

## Modifying the Example

You can modify this example by:
- Changing the message size generation
- Adding more network scenarios with different parameters
- Implementing more complex network topologies
- Simulating variable network conditions that change during the simulation