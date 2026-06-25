"""
SubnetTrafficProfile — aggregate flow generator for an entire subnet.

Replaces per-device TrafficGenerator + WeightedDestSelector + BytesSampler
chains with a single generator that statistically matches the subnet's
traffic distribution. At 100K devices across 500 subnets, this reduces
the DAG from 300K+ nodes to ~500 generators.

How it works:
  - For each sim hour, the aggregate flow rate (flows/sec) determines the
    interarrival time via Exponential sampling (Poisson process).
  - Each flow gets a random source IP from the subnet CIDR range.
  - Destination (ip, port, protocol, qos_class) is sampled from the
    aggregated weighted destination table for that hour.
  - Bytes and packets are sampled from per-destination lognormal profiles,
    the same format as BytesSampler.
  - Output messages match the BytesSampler output format, so they wire
    directly into NetworkSegment or SubnetAggregator.

YAML usage:
    SubnetProfile_Engineering:
      type: SubnetTrafficProfile
      subnet_name: Engineering
      subnet_cidr: "10.1.1.0/24"
      device_count: 200
      initial_ttl: 64
      profiles:
        BIZ_8:
          aggregate_flow_rate: 45.3   # flows/sec for entire subnet
          duration_log_mean: 1.2
          duration_log_variance: 0.8
      destinations:
        BIZ_8:
          - ip: "8.8.8.8"
            port: 443
            protocol: tcp
            weight: 0.34
            qos_class: AF
          - ip: "1.1.1.1"
            port: 53
            protocol: udp
            weight: 0.21
            qos_class: BE
      bytes_profiles:
        "8.8.8.8":
          bytes_log_mean: 7.2
          bytes_log_variance: 1.5
          packets_log_mean: 3.1
          packets_log_variance: 0.8
          response_ratio: 5.2
          rtt_ms_mean: 25.0
          rtt_ms_variance: 30.0
      start_node_active: true
      Seg_Router: ~
"""
import datetime
import math
import random
import uuid

from simpy.core import Environment
from nodes.core.base import BaseNode
from typing import Dict, Any, List, Optional, Callable, Tuple


# Default base epoch: Monday 2025-01-06 00:00:00 UTC
DEFAULT_BASE_EPOCH = datetime.datetime(
    2025, 1, 6, 0, 0, 0, tzinfo=datetime.timezone.utc
).timestamp()


def parse_cidr_range(cidr: str) -> Tuple[int, int]:
    """Parse a CIDR string and return (network_int, broadcast_int) for the
    usable host range (excludes network and broadcast addresses)."""
    parts = cidr.split("/")
    ip_str = parts[0]
    prefix_len = int(parts[1]) if len(parts) > 1 else 24

    octets = ip_str.split(".")
    ip_int = (int(octets[0]) << 24) | (int(octets[1]) << 16) | \
             (int(octets[2]) << 8) | int(octets[3])

    host_bits = 32 - prefix_len
    network = ip_int & (0xFFFFFFFF << host_bits)
    # First usable host = network + 1, last = broadcast - 1
    first_host = network + 1
    last_host = network + (1 << host_bits) - 2

    return first_host, last_host


def int_to_ip(ip_int: int) -> str:
    """Convert a 32-bit integer to dotted-quad IP string."""
    return f"{(ip_int >> 24) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 8) & 0xFF}.{ip_int & 0xFF}"


class SubnetTrafficProfile(BaseNode):
    """Generates aggregate traffic for an entire subnet based on
    distribution profiles computed from per-device data."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.subnet_name: str = configuration.get("subnet_name", "Unknown")
        self.subnet_cidr: str = configuration.get("subnet_cidr", "10.0.0.0/24")
        self.device_count: int = int(configuration.get("device_count", 1))
        self.initial_ttl: int = int(configuration.get("initial_ttl", 64))

        self.profiles: Dict[str, Dict[str, Any]] = configuration.get("profiles", {})
        self.day_type: str = configuration.get("day_type", "BIZ")
        self.sim_hours: float = float(configuration.get("sim_hours", 24))
        self.sim_seconds: float = self.sim_hours * 3600.0
        self.start_hour: int = int(configuration.get("start_hour", 0))
        self.base_epoch: float = float(configuration.get("base_epoch", DEFAULT_BASE_EPOCH))
        self.base_epoch += self.start_hour * 3600

        # Destination tables: same format as WeightedDestSelector
        raw_destinations: Dict[str, List[Dict]] = configuration.get("destinations", {})
        self.dest_tables: Dict[str, List[Tuple[float, Dict]]] = {}
        for key, dest_list in raw_destinations.items():
            if not dest_list:
                continue
            cumulative = []
            running = 0.0
            for entry in dest_list:
                running += float(entry.get("weight", 0))
                cumulative.append((running, entry))
            if running > 0:
                cumulative = [(w / running, e) for w, e in cumulative]
            self.dest_tables[key] = cumulative

        # Bytes profiles: same format as BytesSampler
        self.bytes_profiles: Dict[str, Dict[str, Any]] = configuration.get(
            "bytes_profiles", {}
        )
        self.default_bytes_profile = {
            "bytes_log_mean": 6.0,
            "bytes_log_variance": 2.0,
            "packets_log_mean": 1.5,
            "packets_log_variance": 1.0,
            "response_ratio": 2.0,
        }

        # Parse CIDR for source IP sampling
        self._ip_first, self._ip_last = parse_cidr_range(self.subnet_cidr)

        self._start_node_active: Callable = self.setBoolFromConfig(
            "start_node_active", True
        )

        # Deterministic RNG
        global_seed = int(configuration.get("seed", 42))
        self.rng = random.Random(f"{global_seed}_{name}")

        # Pre-select a fixed pool of active host IPs from the CIDR.
        # Without this, _sample_source_ip draws from the entire range and
        # over an 8-hour sim every IP in a /24 appears at least once,
        # inflating device counts to 254 regardless of device_count.
        cidr_size = self._ip_last - self._ip_first + 1
        pool_size = min(self.device_count, cidr_size)
        all_ips = list(range(self._ip_first, self._ip_last + 1))
        self.rng.shuffle(all_ips)
        self._ip_pool = all_ips[:pool_size]

        # Pre-compute active hours
        self.active_hours = set()
        for key in self.profiles:
            parts = key.rsplit("_", 1)
            if len(parts) == 2:
                try:
                    self.active_hours.add(int(parts[1]))
                except ValueError:
                    pass

        self.env.process(self.run())

    def _sample_source_ip(self) -> str:
        """Sample a random host IP from the pre-selected active device pool."""
        ip_int = self.rng.choice(self._ip_pool)
        return int_to_ip(ip_int)

    def _pick_destination(self, hour: int) -> Optional[Dict]:
        """Pick a destination entry for the given hour using weighted random."""
        key = f"{self.day_type}_{hour}"
        table = self.dest_tables.get(key)
        if not table:
            return None
        r = self.rng.random()
        for cum_weight, entry in table:
            if r <= cum_weight:
                return entry
        return table[-1][1] if table else None

    def _sample_lognormal(self, log_mean: float, log_var: float) -> float:
        """Sample from lognormal given log-space mean and variance."""
        if log_mean is None:
            log_mean = 0.0
        if log_var is None or log_var <= 0:
            return max(1.0, math.exp(log_mean))
        log_std = math.sqrt(log_var)
        return max(1.0, math.exp(self.rng.gauss(log_mean, log_std)))

    def _sample_bytes(self, dst_ip: str) -> Dict[str, Any]:
        """Sample bytes, packets, and optional RTT for a destination."""
        profile = self.bytes_profiles.get(dst_ip, self.default_bytes_profile)

        orig_bytes = int(self._sample_lognormal(
            profile.get("bytes_log_mean"),
            profile.get("bytes_log_variance"),
        ))
        orig_pkts = max(1, int(self._sample_lognormal(
            profile.get("packets_log_mean"),
            profile.get("packets_log_variance"),
        )))
        resp_ratio = profile.get("response_ratio") or 1.0
        resp_bytes = int(orig_bytes * resp_ratio)
        resp_pkts = max(1, int(orig_pkts * resp_ratio * 0.8))

        result = {
            "orig_bytes": orig_bytes,
            "resp_bytes": resp_bytes,
            "orig_pkts": orig_pkts,
            "resp_pkts": resp_pkts,
        }

        # RTT sampling
        rtt_mean = profile.get("rtt_ms_mean")
        if rtt_mean is not None and rtt_mean > 0:
            rtt_var = profile.get("rtt_ms_variance") or 0.0
            if rtt_var > 0:
                mu = math.log(rtt_mean**2 / math.sqrt(rtt_var + rtt_mean**2))
                sigma = math.sqrt(math.log(1 + rtt_var / rtt_mean**2))
                result["tcp_handshake_ms"] = round(max(0.1, math.exp(
                    self.rng.gauss(mu, sigma)
                )), 3)
            else:
                result["tcp_handshake_ms"] = round(rtt_mean, 3)

        return result

    def _sample_duration(self, profile: Dict[str, Any]) -> float:
        """Sample flow duration from lognormal distribution."""
        log_mean = profile.get("duration_log_mean", 0.0) or 0.0
        log_var = profile.get("duration_log_variance", 0.0) or 0.0
        log_std = math.sqrt(log_var) if log_var > 0 else 0.0
        if log_std > 0:
            duration = math.exp(self.rng.gauss(log_mean, log_std))
        else:
            duration = math.exp(log_mean) if log_mean != 0 else 1.0
        return max(0.001, min(duration, 3600.0))

    def _find_next_active_time(self, current_time: float) -> Optional[float]:
        """Find the sim time when the next active hour starts."""
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

    def execute(self):
        """Execute generator — yields (delay, processing_time, data_out_list).

        Models the subnet as a Poisson process: the aggregate flow rate
        across all devices determines the interarrival time (Exponential).
        Each flow gets a random source IP, destination, and byte volume.
        """
        # Prime the generator
        yield 0.0, 0.0, []

        flow_count = 0

        while True:
            current_time = self.env.now

            if current_time >= self.sim_seconds:
                yield BaseNode.stop_signal, 0.0, [
                    {"ID": "stop", self.msg_size_key: 0}
                ]
                return

            # Find current hour and profile
            hour = (int(current_time / 3600) + self.start_hour) % 24
            key = f"{self.day_type}_{hour}"
            profile = self.profiles.get(key)

            if not profile:
                next_active = self._find_next_active_time(current_time)
                if next_active is None:
                    yield BaseNode.stop_signal, 0.0, [
                        {"ID": "stop", self.msg_size_key: 0}
                    ]
                    return

                skip_delay = max(next_active - current_time, 0.001)
                flow_count += 1
                flow_id = str(uuid.UUID(int=self.rng.getrandbits(128)))
                placeholder = {
                    "ID": flow_id,
                    self.msg_size_key: 0,
                    "src_ip": self._sample_source_ip(),
                    "subnet": self.subnet_name,
                    "flow_start": self.base_epoch + next_active,
                    "duration": 0.1,
                    "_skip": True,
                }
                yield skip_delay, 0.0, [placeholder]
                continue

            # Sample interarrival from Exponential (Poisson process)
            aggregate_flow_rate = profile.get("aggregate_flow_rate", 1.0) or 1.0
            interarrival = self.rng.expovariate(aggregate_flow_rate)
            # Clamp: minimum 0.01 second, maximum 1 hour
            interarrival = max(0.01, min(interarrival, 3600.0))

            if current_time + interarrival >= self.sim_seconds:
                yield BaseNode.stop_signal, 0.0, [
                    {"ID": "stop", self.msg_size_key: 0}
                ]
                return

            # Sample source IP from subnet CIDR
            src_ip = self._sample_source_ip()

            # Sample destination
            dest = self._pick_destination(hour)
            if dest:
                dst_ip = dest.get("ip", "0.0.0.0")
                dst_port = int(dest.get("port", 0))
                proto = dest.get("protocol", "tcp")
                if isinstance(proto, int):
                    proto = {1: "icmp", 6: "tcp", 17: "udp"}.get(proto, "tcp")
                qos = dest.get("qos_class", "BE")
                if qos not in ("EF", "AF", "BE"):
                    qos = "BE"
            else:
                dst_ip = "0.0.0.0"
                dst_port = 0
                proto = "tcp"
                qos = "BE"

            # Sample bytes and packets
            byte_data = self._sample_bytes(dst_ip)
            total_bytes = byte_data["orig_bytes"] + byte_data["resp_bytes"]

            # Sample duration
            duration = self._sample_duration(profile)

            # Build flow message (same format as BytesSampler output)
            flow_count += 1
            flow_id = str(uuid.UUID(int=self.rng.getrandbits(128)))
            epoch_ts = self.base_epoch + current_time + interarrival

            flow_msg = {
                "ID": flow_id,
                self.msg_size_key: total_bytes,
                "src_ip": src_ip,
                "subnet": self.subnet_name,
                "flow_start": epoch_ts,
                "duration": duration,
                "flow_count": flow_count,
                "initial_ttl": self.initial_ttl,
                "ttl": self.initial_ttl,
                "dst_ip": dst_ip,
                "dst_port": dst_port,
                "protocol": str(proto),
                "qos_class": qos,
                "orig_bytes": byte_data["orig_bytes"],
                "resp_bytes": byte_data["resp_bytes"],
                "orig_pkts": byte_data["orig_pkts"],
                "resp_pkts": byte_data["resp_pkts"],
            }

            if "tcp_handshake_ms" in byte_data:
                flow_msg["tcp_handshake_ms"] = byte_data["tcp_handshake_ms"]

            print(
                self.log_prefix(flow_id)
                + f"Flow #{flow_count} subnet={self.subnet_name} "
                + f"src={src_ip} dst={dst_ip}:{dst_port}/{proto} "
                + f"bytes={total_bytes} qos={qos} ia={interarrival:.2f}s"
            )

            yield interarrival, 0.0, [flow_msg]
