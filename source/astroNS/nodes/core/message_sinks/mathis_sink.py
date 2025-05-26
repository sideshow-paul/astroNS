"""
Implementation of MathisSink node for displaying Mathis throughput model results.
"""

import sys
import os
from typing import Dict, List, Tuple, Any, Callable, Optional, Union as typeUnion

from nodes.core.base import BaseNode
from simpy.core import Environment


class MathisSink(BaseNode):
    """
    MathisSink node displays the results of the Mathis throughput model simulation.
    It formats and displays network parameters and throughput results in a readable format.
    """

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize the MathisSink node with configuration from YAML"""
        super().__init__(env, name, configuration, self.execute())

        # Load configuration parameters with defaults
        self._time_delay: float = self.setFloatFromConfig(
            "time_delay", 0.0  # Default time delay
        )

        # Get the scenario name for display purposes
        self._scenario_name: str = configuration.get("scenario_name", "Unnamed Scenario")

        # Whether to display network parameters in output
        self._display_network_params: bool = configuration.get("display_network_params", True)

        # Message size key, from the DEFAULT section
        self.msg_size_key: str = configuration.get("msg_size_key", "msg_size")

        # Initialize the process
        self.env.process(self.run())

    @property
    def time_delay(self) -> float:
        """Get the configured time delay"""
        return self._time_delay()

    @property
    def scenario_name(self) -> str:
        """Get the scenario name"""
        return self._scenario_name

    @property
    def display_network_params(self) -> bool:
        """Whether to display network parameters"""
        return self._display_network_params

    def format_network_parameters(self, data: Dict[str, Any]) -> str:
        """Format network parameters for display"""
        if not self.display_network_params:
            return ""

        # Check if all required keys are present
        required_keys = ["mss", "rtt", "packet_loss", "c_constant"]
        if not all(key in data for key in required_keys):
            missing_keys = [key for key in required_keys if key not in data]
            return f"\nNetwork Parameters (incomplete):\nMissing parameters: {', '.join(missing_keys)}\n"

        # Simple table formatting without tabulate dependency
        try:
            output = "\nNetwork Parameters:\n" + "-" * 40 + "\n"
            output += f"MSS:         {data['mss']:.0f} bytes\n"
            output += f"RTT:         {data['rtt'] * 1000:.1f} ms\n"
            output += f"Packet Loss: {data['packet_loss'] * 100:.4f}%\n"
            output += f"C Constant:  {data['c_constant']:.2f}\n"
            output += "-" * 40
            return output
        except (TypeError, ValueError) as e:
            return f"\nNetwork Parameters (error):\nError formatting parameters: {str(e)}\n"

    def format_throughput_results(self, data: Dict[str, Any]) -> str:
        """Format throughput results for display"""
        try:
            output = "\nThroughput Results:\n" + "-" * 40 + "\n"

            # Track if we have any data to display
            has_data = False

            if "throughput" in data:
                output += f"Raw Throughput:   {data['throughput']:.2f} bytes/s\n"
                has_data = True

            if "throughput_mbps" in data:
                output += f"Throughput:       {data['throughput_mbps']:.2f} Mbps\n"
                has_data = True

            if self.msg_size_key in data:
                output += f"Message Size:     {data[self.msg_size_key]:,} bytes\n"
                has_data = True

            if "processing_time" in data:
                output += f"Processing Time:  {data['processing_time']:.2f} seconds\n"
                has_data = True

            if "readable_delay" in data:
                output += f"Transfer Time:    {data['readable_delay']}\n"
                has_data = True

            if not has_data:
                output += "No throughput data available\n"

            output += "-" * 40

            return output
        except Exception as e:
            return f"\nThroughput Results (error):\nError formatting results: {str(e)}\n" + "-" * 40

    def execute(self):
        """Execute function for the MathisSink node"""
        delay: float = 0.0
        processing_time: float = 0.0
        data_in: Dict[str, Any]
        data_out_list: List[Dict[str, Any]] = []

        while True:
            data_in = yield #(delay, processing_time, data_out_list)

            if data_in:
                try:
                    # Set processing time based on configuration
                    #processing_time = self.time_delay

                    # Format output
                    separator = "=" * 60
                    header = f"\n{separator}\n{self.scenario_name}\n{separator}"

                    network_params = self.format_network_parameters(data_in)
                    throughput_results = self.format_throughput_results(data_in)

                    # Build the complete output message
                    output_message = f"{header}\n{network_params}\n{throughput_results}\n{separator}"

                    # Get message ID with fallback
                    msg_id = data_in.get("ID", "unknown")

                    # Log the results
                    print(
                        self.log_prefix(msg_id)
                        + f"Received message at simulation time {self.env.now:.2f}\n"
                        + output_message
                    )
                except Exception as e:
                    print(self.log_prefix() + f"Error processing message: {str(e)}")

                # No output is produced by sink nodes
                data_out_list = []
            else:
                data_out_list = []
