"""
Example script demonstrating the use of MathisThroughputDelay node in a simulation.
This example creates a simple network with a source and a sink, connected through
a MathisThroughputDelay node that models TCP throughput using the Mathis equation.
"""

import simpy
import random
from typing import Dict, Any

from astroNS.nodes.core.base import Source, Sink
from astroNS.nodes.core.network.mathis_delay import MathisThroughputDelay
from astroNS.links import Link


def generate_message(env: simpy.Environment, msg_id: int) -> Dict[str, Any]:
    """Generate a message with random size between 1KB and 10MB"""
    # Generate random message size between 1KB and 10MB
    msg_size = random.randint(1024, 10 * 1024 * 1024)
    
    return {
        "ID": msg_id,
        "msg_size": msg_size,
        "creation_time": env.now,
        "source_time": env.now
    }


def main():
    # Create simulation environment
    env = simpy.Environment()
    
    # Create source node that generates messages with random sizes
    source_config = {
        "generation_interval": 10.0,  # Generate a message every 10 time units
        "message_generator": generate_message
    }
    source = Source(env, "Source", source_config)
    
    # Create MathisThroughputDelay node with custom network parameters
    mathis_config = {
        "mss": 1460.0,        # MSS in bytes (typical for Ethernet)
        "rtt": 0.1,           # RTT in seconds (100ms)
        "packet_loss": 0.001, # Packet loss rate of 0.1%
        "c_constant": 0.93    # Constant for TCP Reno
    }
    mathis_delay = MathisThroughputDelay(env, "MathisDelay", mathis_config)
    
    # Create sink node
    sink_config = {}
    sink = Sink(env, "Sink", sink_config)
    
    # Connect nodes with links
    source_to_mathis = Link(env, "SourceToMathis")
    source_to_mathis.connect(source, mathis_delay)
    
    mathis_to_sink = Link(env, "MathisToSink")
    mathis_to_sink.connect(mathis_delay, sink)
    
    # Different network scenarios to demonstrate
    scenarios = [
        {"name": "Low latency, low loss", "rtt": 0.02, "loss": 0.0001},  # 20ms RTT, 0.01% loss
        {"name": "High latency, low loss", "rtt": 0.2, "loss": 0.0001},  # 200ms RTT, 0.01% loss
        {"name": "Low latency, high loss", "rtt": 0.02, "loss": 0.01},   # 20ms RTT, 1% loss
        {"name": "High latency, high loss", "rtt": 0.2, "loss": 0.01},   # 200ms RTT, 1% loss
    ]
    
    # Run simulation for each scenario
    for i, scenario in enumerate(scenarios):
        print(f"\n=== Scenario {i+1}: {scenario['name']} ===")
        
        # Update node parameters
        mathis_delay._rtt = lambda rtt=scenario["rtt"]: rtt
        mathis_delay._packet_loss = lambda loss=scenario["loss"]: loss
        
        # Calculate theoretical throughput
        throughput = mathis_delay.calculate_throughput()
        print(f"Theoretical throughput: {throughput:.2f} bytes/sec "
              f"({throughput*8/1000000:.2f} Mbps)")
        
        # Reset environment and run simulation for 60 time units
        env = simpy.Environment()
        env.run(until=60)
        
        print(f"=== End of Scenario {i+1} ===\n")

if __name__ == "__main__":
    main()