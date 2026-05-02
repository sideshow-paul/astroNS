"""
WeightedDestSelector — categorical destination picker per device/hour.

Receives flow messages from TrafficGenerator and adds destination IP,
port, and protocol fields based on weighted categorical distributions
observed per (day_type, hour_of_day).

YAML usage:
    Dest_10_0_1_50:
      type: WeightedDestSelector
      device_ip: "10.0.1.50"
      destinations:
        BIZ_8:
          - ip: "8.8.8.8"
            port: 443
            protocol: tcp
            weight: 0.34
          - ip: "1.1.1.1"
            port: 53
            protocol: udp
            weight: 0.21
      Bytes_10_0_1_50: ~
"""
import math
import random

from simpy.core import Environment
from nodes.core.base import BaseNode
from typing import Dict, Any, List, Optional, Callable, Tuple


class WeightedDestSelector(BaseNode):
    """Picks a destination (ip, port, protocol) for each flow based on
    a per-hour categorical weight distribution."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.device_ip: str = configuration.get("device_ip", "0.0.0.0")
        self.day_type: str = configuration.get("day_type", "BIZ")
        raw_destinations: Dict[str, List[Dict]] = configuration.get("destinations", {})

        # Pre-compute cumulative weight tables for efficient sampling
        self.dest_tables: Dict[str, List[Tuple[float, Dict]]] = {}
        for key, dest_list in raw_destinations.items():
            if not dest_list:
                continue
            cumulative = []
            running = 0.0
            for entry in dest_list:
                running += float(entry.get("weight", 0))
                cumulative.append((running, entry))
            # Normalize
            if running > 0:
                cumulative = [(w / running, e) for w, e in cumulative]
            self.dest_tables[key] = cumulative

        # Deterministic RNG
        global_seed = int(configuration.get("seed", 42))
        self.rng = random.Random(f"{global_seed}_{name}")

        self.env.process(self.run())

    def _pick_destination(self, hour: int) -> Optional[Dict]:
        """Pick a destination entry for the given hour using weighted random."""
        key = f"{self.day_type}_{hour}"
        table = self.dest_tables.get(key)
        if not table:
            # Try without day_type prefix as fallback
            return None

        r = self.rng.random()
        for cum_weight, entry in table:
            if r <= cum_weight:
                return entry
        # Fallback to last entry
        return table[-1][1] if table else None

    def execute(self):
        """Execute generator — receives flow messages, adds destination."""
        processing_time: float = 0.0
        data_out_list: List[Dict] = []

        while True:
            data_in = yield (0, processing_time, data_out_list)

            if data_in:
                # Skip placeholder flows
                if data_in.get("_skip"):
                    data_out_list = [data_in.copy()]
                    processing_time = 0.0
                    continue

                # Determine current hour from flow_start
                flow_start = data_in.get("flow_start", 0)
                if flow_start > 1e9:
                    # Epoch timestamp — extract hour
                    import datetime as dt
                    hour = dt.datetime.fromtimestamp(
                        flow_start, tz=dt.timezone.utc
                    ).hour
                else:
                    hour = int(self.env.now / 3600) % 24

                dest = self._pick_destination(hour)

                data_out = data_in.copy()
                if dest:
                    data_out["dst_ip"] = dest.get("ip", "0.0.0.0")
                    data_out["dst_port"] = int(dest.get("port", 0))
                    proto = dest.get("protocol", "tcp")
                    if isinstance(proto, int):
                        proto = {1: "icmp", 6: "tcp", 17: "udp"}.get(proto, "tcp")
                    data_out["protocol"] = str(proto)
                else:
                    # No destination table — assign defaults
                    data_out["dst_ip"] = "0.0.0.0"
                    data_out["dst_port"] = 0
                    data_out["protocol"] = "tcp"

                processing_time = 0.0
                data_out_list = [data_out]

                print(
                    self.log_prefix(data_in["ID"])
                    + f"Dest selected: {data_out['dst_ip']}:{data_out['dst_port']}/{data_out['protocol']}"
                )
            else:
                data_out_list = []
                processing_time = 0.0
