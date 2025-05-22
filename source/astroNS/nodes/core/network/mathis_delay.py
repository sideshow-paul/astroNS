"""
Mathis Throughput Delay is a node that calculates transmission delay based on the Mathis equation.
This node considers packet loss, RTT, and MSS to realistically model TCP throughput.
"""

import math
import sys
import os
from typing import Dict, List, Tuple, Any, Callable, Optional, Union as typeUnion

from nodes.core.base import BaseNode
from simpy.core import Environment

# Import functions from network_throughput.py
try:
    from astroNS.nodes.core.network.network_throughput import calculate_throughput_mathis, estimate_transfer_time, format_time
except ImportError:
    # Fallback implementation if the module is not available
    def calculate_throughput_mathis(mss, rtt, packet_loss, c=0.93):
        """Calculate maximum TCP throughput using the Mathis equation."""
        if packet_loss < 1e-10:
            return float('inf')
        return (mss * c) / (rtt * math.sqrt(packet_loss))
    
    def estimate_transfer_time(file_size, throughput):
        """Estimate time to transfer a file with the given throughput."""
        return file_size / throughput if throughput > 0 else float('inf')
    
    def format_time(seconds):
        """Format time in seconds to a human-readable format."""
        if seconds < 1:
            return f"{seconds*1000:.2f} ms"
        elif seconds < 60:
            return f"{seconds:.2f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.2f} minutes"
        else:
            return f"{seconds/3600:.2f} hours"


class MathisThroughputDelay(BaseNode):
    """
    MathisThroughputDelay is a delay node that calculates transmission delay based on 
    the Mathis equation for TCP throughput considering packet loss, RTT, and MSS.
    """

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize the MathisThroughputDelay node with configuration from YAML"""
        super().__init__(env, name, configuration, self.execute())
        
        # Load all parameters from configuration with defaults
        self._mss: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "mss", 1460.0  # Default MSS for Ethernet in bytes
        )
        
        self._rtt: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "rtt", 0.1  # Default RTT of 100ms
        )
        
        self._packet_loss: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "packet_loss", 0.001  # Default packet loss of 0.1%
        )
        
        self._c_constant: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "c_constant", 0.93  # Default constant for TCP Reno
        )
        
        self._time_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_delay", 0.0  # Default time delay
        )
        
        # Initialize any required imports
        self.required_imports = "import math; import datetime;"
        self.fns: Dict[str, Any] = {}
        exec(self.required_imports, self.fns)
        
        # Output keys
        self._output_keys = configuration.get("output_keys", [
            "throughput", "throughput_mbps", "processing_time", "readable_delay"
        ])
        
        # Initialize the process
        self.env.process(self.run())

    @property
    def mss(self) -> Optional[float]:
        """Maximum Segment Size in bytes"""
        return self._mss()
    
    @property
    def rtt(self) -> Optional[float]:
        """Round Trip Time in seconds"""
        return self._rtt()
    
    @property
    def packet_loss(self) -> Optional[float]:
        """Packet loss probability as a decimal"""
        return self._packet_loss()
    
    @property
    def c_constant(self) -> Optional[float]:
        """Constant C in Mathis equation"""
        return self._c_constant()
    
    @property
    def time_delay(self) -> Optional[float]:
        """Get the configured time delay"""
        return self._time_delay()

    @property
    def output_keys(self) -> List[str]:
        """Get the list of output keys to add to the message"""
        return self._output_keys

    def get_param(self, msg: Dict[str, Any], param_name: str) -> float:
        """
        Get a parameter value, prioritizing the message, then node properties
        
        This allows parameters to be dynamically set in the message by upstream nodes
        or to be set statically in the YAML configuration.
        """
        # First check if parameter is in the message
        if param_name in msg:
            return float(msg[param_name])
        
        # Then use the node property
        elif hasattr(self, param_name):
            return getattr(self, param_name)
        
        # This should not happen as all parameters have defaults
        else:
            print(f"Warning: Parameter {param_name} not found in message or node properties")
            return 0.0

    def calculate_throughput(self, msg: Dict[str, Any]) -> float:
        """Calculate the network throughput using the Mathis equation"""
        try:
            mss = self.get_param(msg, "mss")
            rtt = self.get_param(msg, "rtt")
            packet_loss = self.get_param(msg, "packet_loss")
            c_constant = self.get_param(msg, "c_constant")
            
            return calculate_throughput_mathis(mss, rtt, packet_loss, c_constant)
        except ValueError as e:
            print(f"{self.name} Error calculating throughput: {e}")
            # Return a very small throughput as fallback
            return 1.0  # 1 byte per second as a fallback
    
    def calculate_delay(self, message_size: float, throughput: float) -> float:
        """Calculate the delay for a given message size"""
        return estimate_transfer_time(message_size, throughput)

    def execute(self):
        """Execute function for the MathisThroughputDelay node"""
        delay: float = 0.0
        processing_time: float = 0.0
        data_in: Dict[str, Any]
        data_out_list: List[Dict[str, Any]] = []
        
        while True:
            data_in = yield (delay, processing_time, data_out_list)
            
            if data_in:
                # Get the message size from the input data
                message_size = data_in[self.msg_size_key]
                
                # Calculate network throughput using Mathis equation
                throughput = self.calculate_throughput(data_in)
                
                # Calculate delay based on message size and throughput
                delay = self.calculate_delay(message_size, throughput)
                
                # Set processing time to the calculated delay
                processing_time = delay
                
                # Create a copy of the input data for output
                data_out = data_in.copy()
                
                # Add calculated values to the message based on output_keys
                if "throughput" in self.output_keys:
                    data_out["throughput"] = throughput
                
                if "throughput_mbps" in self.output_keys:
                    data_out["throughput_mbps"] = throughput * 8 / 1000000
                
                if "processing_time" in self.output_keys:
                    data_out["processing_time"] = delay
                
                if "readable_delay" in self.output_keys:
                    data_out["readable_delay"] = format_time(delay)
                
                # Add network parameters to the output message if requested
                if self.configuration.get("save_network_params", False):
                    for param in ["mss", "rtt", "packet_loss", "c_constant"]:
                        if param not in data_out:
                            data_out[param] = self.get_param(data_in, param)
                
                data_out_list = [data_out]
                
                # Get network parameters for logging - use message values if available, 
                # otherwise use the node's configured values
                mss = self.get_param(data_in, "mss")
                rtt = self.get_param(data_in, "rtt")
                packet_loss = self.get_param(data_in, "packet_loss")
                c_constant = self.get_param(data_in, "c_constant")
                
                # Log the processing information
                print(
                    self.log_prefix(data_in["ID"])
                    + f"Data size of |{message_size}| arrived at |{self.env.now}|. "
                    + f"Network params: MSS={mss}, RTT={rtt}s, "
                    + f"Loss={packet_loss*100}%, C={c_constant}. "
                    + f"Throughput: {throughput:.2f} B/s ({throughput*8/1000000:.2f} Mbps). "
                    + f"Processing took |{delay}| simtime units"
                )
            else:
                data_out_list = []