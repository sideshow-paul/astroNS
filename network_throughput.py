
# NOTE: This file has been moved to source/astroNS/nodes/core/network/network_throughput.py
# Please use the new location for any imports or modifications.

#  Python function to calculate network throughput using the Mathis equation. The Mathis equation describes the maximum TCP throughput achievable over a network with a given packet loss rate.

# The Mathis equation is:
# Throughput ≤ (MSS * C) / (RTT * sqrt(p))

# Where:
# - MSS = Maximum Segment Size (in bytes)
# - RTT = Round Trip Time (in seconds)
# - p = Packet loss probability (as a decimal, e.g., 0.01 for 1%)
# - C = Constant (typically around 0.93 for TCP Reno)


import math

def calculate_throughput_mathis(mss, rtt, packet_loss, c=0.93):
    """
    Calculate maximum TCP throughput using the Mathis equation.

    The Mathis equation models TCP throughput as:
    Throughput ≤ (MSS * C) / (RTT * sqrt(p))

    Args:
        mss (float): Maximum Segment Size in bytes.
        rtt (float): Round Trip Time in seconds.
        packet_loss (float): Packet loss probability as a decimal (e.g., 0.01 for 1%).
        c (float, optional): Constant (typically 0.93 for TCP Reno). Defaults to 0.93.

    Returns:
        float: Maximum TCP throughput in bytes per second.

    Raises:
        ValueError: If any of the input parameters are invalid.
    """
    # Input validation
    if mss <= 0:
        raise ValueError("MSS must be positive")
    if rtt <= 0:
        raise ValueError("RTT must be positive")
    if packet_loss <= 0:
        raise ValueError("Packet loss probability must be positive")
    if c <= 0:
        raise ValueError("Constant C must be positive")

    # Handle edge case where packet loss is too small (would cause division by zero)
    if packet_loss < 1e-10:
        return float('inf')  # Practically unlimited throughput

    # Calculate throughput using Mathis equation
    throughput = (mss * c) / (rtt * math.sqrt(packet_loss))

    return throughput

def throughput_to_human_readable(throughput_bytes_per_sec):
    """
    Convert throughput in bytes per second to a human-readable format.

    Args:
        throughput_bytes_per_sec (float): Throughput in bytes per second.

    Returns:
        str: Human-readable throughput with appropriate units.
    """
    units = ['bps', 'Kbps', 'Mbps', 'Gbps', 'Tbps']

    # Convert bytes to bits
    throughput_bits_per_sec = throughput_bytes_per_sec * 8

    unit_index = 0
    while throughput_bits_per_sec >= 1000 and unit_index < len(units) - 1:
        throughput_bits_per_sec /= 1000
        unit_index += 1

    return f"{throughput_bits_per_sec:.2f} {units[unit_index]}"

def example_usage():
    """
    Example usage of the Mathis equation throughput calculator.
    """
    # Example parameters
    mss = 1460  # bytes (typical MSS for Ethernet)
    rtt = 0.1   # seconds (100ms)
    packet_loss = 0.001  # 0.1% packet loss
    
    # Example file sizes
    small_file_size = 1024 * 1024  # 1 MB
    large_file_size = 1024 * 1024 * 1024  # 1 GB

    throughput = calculate_throughput_mathis(mss, rtt, packet_loss)
    readable_throughput = throughput_to_human_readable(throughput)
    
    # Calculate transfer times
    small_file_time = estimate_transfer_time(small_file_size, throughput)
    large_file_time = estimate_transfer_time(large_file_size, throughput)

    print(f"Network Parameters:")
    print(f"  MSS: {mss} bytes")
    print(f"  RTT: {rtt*1000:.2f} ms")
    print(f"  Packet Loss: {packet_loss*100:.4f}%")
    print(f"Maximum Theoretical Throughput: {readable_throughput}")
    print("\nEstimated Transfer Times:")
    print(f"  1 MB file: {format_time(small_file_time)}")
    print(f"  1 GB file: {format_time(large_file_time)}")

def estimate_transfer_time(file_size, throughput):
    """
    Estimate the time required to transfer a file of a given size using the calculated throughput.
    
    Args:
        file_size (float): Size of the file in bytes.
        throughput (float): Network throughput in bytes per second.
    
    Returns:
        float: Estimated time in seconds to transfer the file.
        
    Raises:
        ValueError: If any of the input parameters are invalid.
    """
    # Input validation
    if file_size <= 0:
        raise ValueError("File size must be positive")
    if throughput <= 0:
        raise ValueError("Throughput must be positive")
    
    # Calculate transfer time
    transfer_time = file_size / throughput
    
    return transfer_time

def format_time(seconds):
    """
    Format time in seconds to a human-readable format.
    
    Args:
        seconds (float): Time in seconds.
        
    Returns:
        str: Human-readable time with appropriate units.
    """
    if seconds < 1:
        return f"{seconds*1000:.2f} ms"
    elif seconds < 60:
        return f"{seconds:.2f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.2f} minutes"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.2f} hours"
    else:
        days = seconds / 86400
        return f"{days:.2f} days"

if __name__ == "__main__":
    example_usage()
