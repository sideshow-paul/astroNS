#!/usr/bin/env python
"""
Script to run the Mathis Throughput Example model.

This script sets up the environment and runs the MathisThroughputModel.yml
simulation to demonstrate TCP throughput calculations using the Mathis equation.
"""
import os
import sys
import argparse
from pathlib import Path

# Add the astroNS module to the Python path
current_dir = Path(__file__).parent.absolute()
source_dir = current_dir.parent.parent
if str(source_dir) not in sys.path:
    sys.path.append(str(source_dir))

# Import astroNS
from astroNS.astroNS import main as astro_main

def run_example(duration=100, silent=False):
    """Run the Mathis Throughput example simulation"""
    print("Running Mathis Throughput Example")
    print(f"Simulation duration: {duration} time units")
    
    # Construct the path to the model file
    model_path = os.path.join(current_dir, "MathisThroughputModel.yml")
    
    # Set up command line arguments for astroNS
    args = [
        "-m", model_path,      # Model file
        "-d", str(duration),   # Duration
    ]
    
    if silent:
        args.append("--silent")
    
    # Run the simulation
    sys.argv = ["astroNS.py"] + args
    astro_main()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Mathis Throughput Example")
    parser.add_argument("-d", "--duration", type=int, default=100, 
                        help="Simulation duration in time units (default: 100)")
    parser.add_argument("-s", "--silent", action="store_true",
                        help="Run in silent mode with minimal output")
    
    args = parser.parse_args()
    run_example(duration=args.duration, silent=args.silent)