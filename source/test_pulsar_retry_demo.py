#!/usr/bin/env python3
"""
Demonstration script for PulsarTopicSource retry functionality.
This script shows how the retry logic works in different scenarios.
"""

import sys
import os
import time
import threading
from datetime import datetime

# Add source directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'astroNS'))

class MockEnvironment:
    """Mock SimPy environment for testing"""
    def __init__(self):
        self.now = 0.0
    
    def timeout(self, delay):
        time.sleep(delay / 100)  # Speed up for demo
        self.now += delay

class RetryLogicDemo:
    """Demonstrates the retry logic used in PulsarTopicSource"""
    
    def __init__(self, retry_on_connection_error=True, max_retry_attempts=3, retry_delay_secs=2.0):
        self.retry_on_connection_error = retry_on_connection_error
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay_secs = retry_delay_secs
        self.current_retry_count = 0
        self.last_retry_time = 0.0
        self.env = MockEnvironment()
        self.connected = False
        
    def log_prefix(self):
        return f"[RetryDemo|{self.env.now:6.1f}] "
    
    def _should_retry_connection(self):
        """Determine if we should retry connection based on configuration and timing"""
        if not self.retry_on_connection_error:
            return False
            
        if self.current_retry_count >= self.max_retry_attempts:
            # Check if enough time has passed to reset retry counter
            current_time = self.env.now
            if current_time - self.last_retry_time >= self.retry_delay_secs * self.max_retry_attempts:
                self.current_retry_count = 0
                return True
            return False
        
        return True
    
    def simulate_connection_attempt(self, should_succeed=False):
        """Simulate a connection attempt"""
        if should_succeed:
            print(self.log_prefix() + "✓ Connection successful!")
            self.connected = True
            self.current_retry_count = 0
            return True
        else:
            print(self.log_prefix() + "✗ Connection failed")
            self.connected = False
            return False
    
    def demonstrate_retry_cycle(self, success_on_attempt=None):
        """Demonstrate a complete retry cycle"""
        print(f"\n{self.log_prefix()}Starting retry demonstration")
        print(f"{self.log_prefix()}Config: retry_enabled={self.retry_on_connection_error}, max_attempts={self.max_retry_attempts}, delay={self.retry_delay_secs}s")
        
        attempt = 0
        while not self.connected:
            if self._should_retry_connection():
                attempt += 1
                print(f"{self.log_prefix()}Attempting connection (attempt {self.current_retry_count + 1}/{self.max_retry_attempts})")
                self.current_retry_count += 1
                self.last_retry_time = self.env.now
                
                # Simulate connection attempt
                should_succeed = (success_on_attempt is not None and attempt == success_on_attempt)
                if self.simulate_connection_attempt(should_succeed):
                    break
                
                if self.current_retry_count < self.max_retry_attempts:
                    print(f"{self.log_prefix()}Retrying in {self.retry_delay_secs} seconds...")
                    time.sleep(self.retry_delay_secs / 10)  # Speed up for demo
                    self.env.now += self.retry_delay_secs
                else:
                    print(f"{self.log_prefix()}Maximum retry attempts ({self.max_retry_attempts}) reached")
            else:
                print(f"{self.log_prefix()}Cannot retry: max attempts reached or retry disabled")
                break
        
        if self.connected:
            print(f"{self.log_prefix()}🎉 Connection established successfully!")
        else:
            print(f"{self.log_prefix()}❌ Failed to establish connection")
        
        return self.connected

def run_demonstrations():
    """Run various retry demonstrations"""
    
    print("PulsarTopicSource Retry Logic Demonstration")
    print("=" * 60)
    
    # Demo 1: Successful retry
    print("\n📋 DEMO 1: Connection succeeds on 2nd attempt")
    print("-" * 40)
    demo1 = RetryLogicDemo(retry_on_connection_error=True, max_retry_attempts=3, retry_delay_secs=2.0)
    demo1.demonstrate_retry_cycle(success_on_attempt=2)
    
    # Demo 2: All retries fail
    print("\n📋 DEMO 2: All retry attempts fail")
    print("-" * 40)
    demo2 = RetryLogicDemo(retry_on_connection_error=True, max_retry_attempts=3, retry_delay_secs=1.0)
    demo2.demonstrate_retry_cycle(success_on_attempt=None)
    
    # Demo 3: Retry disabled
    print("\n📋 DEMO 3: Retry disabled")
    print("-" * 40)
    demo3 = RetryLogicDemo(retry_on_connection_error=False, max_retry_attempts=1, retry_delay_secs=5.0)
    demo3.demonstrate_retry_cycle(success_on_attempt=None)
    
    # Demo 4: Aggressive retry settings
    print("\n📋 DEMO 4: Aggressive retry (5 attempts, 0.5s delay)")
    print("-" * 40)
    demo4 = RetryLogicDemo(retry_on_connection_error=True, max_retry_attempts=5, retry_delay_secs=0.5)
    demo4.demonstrate_retry_cycle(success_on_attempt=4)
    
    # Demo 5: Reset retry counter after timeout
    print("\n📋 DEMO 5: Retry counter reset after timeout period")
    print("-" * 40)
    demo5 = RetryLogicDemo(retry_on_connection_error=True, max_retry_attempts=2, retry_delay_secs=1.0)
    
    # First cycle - fail all attempts
    print(f"{demo5.log_prefix()}First retry cycle:")
    demo5.demonstrate_retry_cycle(success_on_attempt=None)
    
    # Simulate time passage to reset retry counter
    print(f"{demo5.log_prefix()}Simulating time passage...")
    reset_time = demo5.retry_delay_secs * demo5.max_retry_attempts + 1
    time.sleep(reset_time / 10)  # Speed up for demo
    demo5.env.now += reset_time
    
    # Second cycle - should be able to retry again
    print(f"{demo5.log_prefix()}Second retry cycle (after reset):")
    demo5.demonstrate_retry_cycle(success_on_attempt=1)

def show_configuration_examples():
    """Show different configuration examples"""
    
    print("\n📋 CONFIGURATION EXAMPLES")
    print("=" * 60)
    
    configs = [
        {
            "name": "Development (Fast retry)",
            "config": {
                "retry_on_connection_error": True,
                "max_retry_attempts": 5,
                "retry_delay_secs": 1.0
            },
            "use_case": "Quick feedback during development"
        },
        {
            "name": "Production (Conservative)",
            "config": {
                "retry_on_connection_error": True,
                "max_retry_attempts": 3,
                "retry_delay_secs": 10.0
            },
            "use_case": "Stable production environment"
        },
        {
            "name": "Critical (Persistent)",
            "config": {
                "retry_on_connection_error": True,
                "max_retry_attempts": 10,
                "retry_delay_secs": 30.0
            },
            "use_case": "Mission-critical systems"
        },
        {
            "name": "Fail-fast (No retry)",
            "config": {
                "retry_on_connection_error": False,
                "max_retry_attempts": 1,
                "retry_delay_secs": 0.0
            },
            "use_case": "Testing or when external monitoring handles retries"
        }
    ]
    
    for config_example in configs:
        print(f"\n{config_example['name']}:")
        print(f"  Use case: {config_example['use_case']}")
        print(f"  Configuration:")
        for key, value in config_example['config'].items():
            print(f"    {key}: {value}")
        
        # Calculate total retry time
        if config_example['config']['retry_on_connection_error']:
            max_time = (config_example['config']['max_retry_attempts'] - 1) * config_example['config']['retry_delay_secs']
            print(f"  Max retry time: {max_time} seconds")
        else:
            print(f"  Max retry time: 0 seconds (immediate fail)")

if __name__ == "__main__":
    try:
        run_demonstrations()
        show_configuration_examples()
        
        print("\n🎯 SUMMARY")
        print("=" * 60)
        print("The retry logic provides:")
        print("• Configurable retry attempts and delays")
        print("• Automatic reset of retry counter after timeout")
        print("• Option to disable retries for fail-fast behavior")
        print("• Graceful handling of connection failures")
        print("• Continuous simulation operation during outages")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo failed with error: {e}")