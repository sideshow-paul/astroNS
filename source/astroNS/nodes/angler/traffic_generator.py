"""
TrafficGenerator — per-device flow source driven by Welford statistics.

Generates synthetic flow events at rates matching observed interarrival
distributions per (day_type, hour_of_day). Each generated message carries
src_ip, flow_start, and duration fields; downstream nodes add destination
and byte volume information.

YAML usage:
    Gen_10_0_1_50:
      type: TrafficGenerator
      device_ip: "10.0.1.50"
      subnet: "IoT"
      profiles:
        BIZ_8:
          interarrival_mean: 12.5
          interarrival_variance: 25.0
          duration_log_mean: 1.2
          duration_log_variance: 0.8
          flow_count_mean: 45.0
          sample_count: 100
      start_node_active: true
      Dest_10_0_1_50: ~
"""
import math
import random
import uuid
import datetime

from simpy.core import Environment
from nodes.core.base import BaseNode
from typing import Dict, Any, List, Optional, Callable


# Default base epoch: Monday 2025-01-06 00:00:00 UTC
DEFAULT_BASE_EPOCH = datetime.datetime(
    2025, 1, 6, 0, 0, 0, tzinfo=datetime.timezone.utc
).timestamp()


class TrafficGenerator(BaseNode):
    """A per-device flow source that generates flows at statistically
    realistic rates based on Welford-computed interarrival distributions."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.device_ip: str = configuration.get("device_ip", "0.0.0.0")
        self.subnet: str = configuration.get("subnet", "Unknown")
        self.profiles: Dict[str, Dict[str, Any]] = configuration.get("profiles", {})
        self.day_type: str = configuration.get("day_type", "BIZ")
        self.sim_hours: float = float(configuration.get("sim_hours", 24))
        self.sim_seconds: float = self.sim_hours * 3600.0
        self.start_hour: int = int(configuration.get("start_hour", 0))
        self.base_epoch: float = float(configuration.get("base_epoch", DEFAULT_BASE_EPOCH))
        # Shift base_epoch so generated timestamps reflect the correct hour of day
        self.base_epoch += self.start_hour * 3600

        # Initial TTL for this device's OS (64=Linux/macOS, 128=Windows, 255=network)
        self.initial_ttl: int = int(configuration.get("initial_ttl", 64))

        self._start_node_active: Callable = self.setBoolFromConfig(
            "start_node_active", True
        )

        # Deterministic RNG per device
        global_seed = int(configuration.get("seed", 42))
        self.rng = random.Random(f"{global_seed}_{name}")

        # Pre-compute which hours have profiles
        self.active_hours = set()
        for key in self.profiles:
            parts = key.rsplit("_", 1)
            if len(parts) == 2:
                try:
                    self.active_hours.add(int(parts[1]))
                except ValueError:
                    pass

        self.env.process(self.run())

    def _find_next_active_time(self, current_time: float) -> Optional[float]:
        """Find the sim time (seconds) when the next active hour starts.
        Returns None if no active hours exist or we've exceeded sim duration."""
        if not self.active_hours:
            return None

        current_hour = int(current_time / 3600)
        for offset_hours in range(25):
            check_hour = current_hour + offset_hours
            if check_hour * 3600 >= self.sim_seconds:
                return None
            hour = (check_hour + self.start_hour) % 24
            if hour in self.active_hours:
                if offset_hours == 0:
                    return current_time
                return check_hour * 3600.0
        return None

    def _sample_interarrival(self, profile: Dict[str, Any]) -> float:
        """Sample interarrival time in seconds from profile stats."""
        mean_sec = profile.get("interarrival_mean", 10.0) or 10.0
        var_sec = profile.get("interarrival_variance", 0.0) or 0.0
        std_sec = math.sqrt(var_sec) if var_sec > 0 else 0.0

        if std_sec > 0:
            sample_sec = self.rng.gauss(mean_sec, std_sec)
        else:
            sample_sec = mean_sec

        # Clamp: minimum 1 second, maximum 1 hour
        return max(1.0, min(sample_sec, 3600.0))

    def _sample_duration(self, profile: Dict[str, Any]) -> float:
        """Sample flow duration in seconds from lognormal distribution."""
        log_mean = profile.get("duration_log_mean", 0.0) or 0.0
        log_var = profile.get("duration_log_variance", 0.0) or 0.0
        log_std = math.sqrt(log_var) if log_var > 0 else 0.0

        if log_std > 0:
            duration = math.exp(self.rng.gauss(log_mean, log_std))
        else:
            duration = math.exp(log_mean) if log_mean != 0 else 1.0

        # Clamp: minimum 0.001s, maximum 1 hour
        return max(0.001, min(duration, 3600.0))

    def execute(self):
        """Execute generator — yields (delay, processing_time, data_out_list)."""
        # Prime the generator (consumed by set_node_exec_generator)
        yield 0.0, 0.0, []

        flow_count = 0

        while True:
            current_time = self.env.now

            # Check simulation bounds
            if current_time >= self.sim_seconds:
                yield BaseNode.stop_signal, 0.0, [
                    {"ID": "stop", self.msg_size_key: 0}
                ]
                return

            # Find current hour and profile (offset by start_hour)
            hour = (int(current_time / 3600) + self.start_hour) % 24
            key = f"{self.day_type}_{hour}"
            profile = self.profiles.get(key)

            if not profile:
                # No profile for this hour — advance to next active hour
                next_active = self._find_next_active_time(current_time)
                if next_active is None:
                    yield BaseNode.stop_signal, 0.0, [
                        {"ID": "stop", self.msg_size_key: 0}
                    ]
                    return

                # Sleep until next active hour boundary
                skip_delay = max(next_active - current_time, 0.001)

                # Generate a placeholder flow to keep the node alive
                # (source nodes stop if data_out_list is empty)
                flow_count += 1
                flow_id = str(uuid.UUID(int=self.rng.getrandbits(128)))
                epoch_ts = self.base_epoch + next_active
                placeholder = {
                    "ID": flow_id,
                    self.msg_size_key: 0,
                    "src_ip": self.device_ip,
                    "subnet": self.subnet,
                    "flow_start": epoch_ts,
                    "duration": 0.1,
                    "_skip": True,
                }
                yield skip_delay, 0.0, [placeholder]
                continue

            # Sample timing
            interarrival = self._sample_interarrival(profile)
            duration = self._sample_duration(profile)

            # Check that the flow won't start past sim end
            if current_time + interarrival >= self.sim_seconds:
                yield BaseNode.stop_signal, 0.0, [
                    {"ID": "stop", self.msg_size_key: 0}
                ]
                return

            # Generate flow event
            flow_count += 1
            flow_id = str(uuid.UUID(int=self.rng.getrandbits(128)))
            epoch_ts = self.base_epoch + current_time + interarrival

            flow_msg = {
                "ID": flow_id,
                self.msg_size_key: 0,  # BytesSampler fills this
                "src_ip": self.device_ip,
                "subnet": self.subnet,
                "flow_start": epoch_ts,
                "duration": duration,
                "flow_count": flow_count,
                "initial_ttl": self.initial_ttl,
                "ttl": self.initial_ttl,  # decremented by NetworkSegment L3 hops
            }

            print(
                self.log_prefix(flow_id)
                + f"Flow #{flow_count} src={self.device_ip} hour={hour} "
                + f"ia={interarrival:.1f}s dur={duration:.2f}s"
            )

            yield interarrival, 0.0, [flow_msg]
