"""
SubnetAggregator — tracks per-subnet bandwidth and forwards to sinks.

Receives fully-assembled flow messages and tracks cumulative bandwidth
per subnet. Optionally logs bandwidth utilization against profiled
percentile thresholds (p95, max). Passes all messages through to
connected output sinks (ZeekConnLogSink, FlowRecordSink).

YAML usage:
    SubnetAgg_IoT:
      type: SubnetAggregator
      subnet_name: "IoT"
      subnet_cidr: "10.0.1.0/24"
      bandwidth_profiles:
        - day_type: BIZ
          hour: 8
          mean_bps: 1200000.0
          p95_bps: 3400000.0
          max_bps: 5000000.0
      ConnLogSink: ~
      FlowSink: ~
"""
from simpy.core import Environment
from nodes.core.base import BaseNode
from typing import Dict, Any, List, Optional, Callable
from collections import defaultdict


class SubnetAggregator(BaseNode):
    """Tracks per-subnet bandwidth usage and forwards flow messages
    to output sinks."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.subnet_name: str = configuration.get("subnet_name", "Unknown")
        self.subnet_cidr: str = configuration.get("subnet_cidr", "0.0.0.0/0")
        raw_bw = configuration.get("bandwidth_profiles") or []

        # Index bandwidth profiles by (day_type, hour) for quick lookup
        self.bw_profiles: Dict[str, Dict[str, float]] = {}
        for entry in raw_bw:
            if isinstance(entry, dict):
                key = f"{entry.get('day_type', 'BIZ')}_{entry.get('hour', 0)}"
                self.bw_profiles[key] = entry

        self.day_type: str = configuration.get("day_type", "BIZ")
        self.start_hour: int = int(configuration.get("start_hour", 0))

        # Bandwidth tracking
        self.total_bytes: int = 0
        self.total_flows: int = 0
        self.hourly_bytes: Dict[int, int] = defaultdict(int)

        self.env.process(self.run())

    def execute(self):
        """Execute generator — receives flow messages, tracks bandwidth,
        and forwards to sinks."""
        processing_time: float = 0.0
        data_out_list: List[Dict] = []

        while True:
            data_in = yield (0, processing_time, data_out_list)

            if data_in:
                data_out = data_in.copy()

                # Skip placeholders
                if not data_in.get("_skip"):
                    # Track bandwidth
                    flow_bytes = (
                        data_in.get("orig_bytes", 0) + data_in.get("resp_bytes", 0)
                    )
                    self.total_bytes += flow_bytes
                    self.total_flows += 1

                    hour = (int(self.env.now / 3600) + self.start_hour) % 24
                    self.hourly_bytes[hour] += flow_bytes

                    # Check against bandwidth profile thresholds
                    bw_key = f"{self.day_type}_{hour}"
                    bw_profile = self.bw_profiles.get(bw_key)
                    if bw_profile and flow_bytes > 0:
                        max_bps = bw_profile.get("max_bps", 0)
                        if max_bps and max_bps > 0:
                            # Convert flow bytes to estimated bps
                            duration = data_in.get("duration", 1.0) or 1.0
                            flow_bps = (flow_bytes * 8) / duration
                            if flow_bps > max_bps:
                                print(
                                    self.log_prefix(data_in["ID"])
                                    + f"BW WARNING: {self.subnet_name} flow "
                                    + f"{flow_bps:.0f} bps > max {max_bps:.0f} bps"
                                )

                    # Tag the message with subnet info
                    data_out["agg_subnet"] = self.subnet_name
                    data_out["agg_total_flows"] = self.total_flows

                processing_time = 0.0
                data_out_list = [data_out]

                if not data_in.get("_skip"):
                    print(
                        self.log_prefix(data_in["ID"])
                        + f"Subnet {self.subnet_name}: flow #{self.total_flows} "
                        + f"total_bytes={self.total_bytes}"
                    )
            else:
                data_out_list = []
                processing_time = 0.0
