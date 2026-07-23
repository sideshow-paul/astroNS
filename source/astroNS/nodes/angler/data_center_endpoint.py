"""
DataCenterEndpoint — models the remote cloud provider endpoint.

Receives flows from its upstream WAN link (NetworkSegment), enriches
them with data center metadata (provider, region, latency), applies
remote-side capacity constraints, and forwards to sinks.

Availability scheduling enables what-if outage scenarios: set
``availability`` to 0.0 for a time window and all flows to that
provider/region are dropped.

YAML usage:
    DC_AWS_us_east:
      type: DataCenterEndpoint
      provider: AWS
      region: us-east-1
      label: "AWS US East (Ashburn)"
      capacity_bps: 10000000000
      availability: 1.0
      outage_windows:
        - start_hour: 4
          end_hour: 5
          availability: 0.0
        - start_hour: 12
          end_hour: 13
          availability: 0.5
      ConnLogSink: ~
      DnsLogSink: ~
      SslLogSink: ~
"""
import random

from simpy.core import Environment
from nodes.core.base import BaseNode
from nodes.angler.hour_windows import active_window
from typing import Dict, Any, List, Optional
from collections import defaultdict


class DataCenterEndpoint(BaseNode):
    """Remote cloud provider endpoint with capacity, availability,
    and what-if outage scheduling."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.provider: str = configuration.get("provider", "Unknown")
        self.region: str = configuration.get("region", "unknown")
        self.label: str = configuration.get("label", f"{self.provider} {self.region}")
        self.capacity_bps: float = float(
            configuration.get("capacity_bps", 10_000_000_000)
        )
        self.default_availability: float = float(
            configuration.get("availability", 1.0)
        )

        # Outage windows: [{start_hour, end_hour, availability}, ...]
        self.outage_windows: List[Dict] = configuration.get("outage_windows") or []

        # Simulation time reference
        self.day_type: str = configuration.get("day_type", "BIZ")
        self.start_hour: int = int(configuration.get("start_hour", 0))

        # Per-second bandwidth tracking
        self._current_second: int = -1
        self._second_bytes: int = 0

        # Statistics
        self.total_flows: int = 0
        self.total_bytes: int = 0
        self.total_dropped: int = 0
        self.total_congestion_delay_ms: float = 0.0

        # Deterministic RNG for availability-based drops
        global_seed = int(configuration.get("seed", 42))
        self.rng = random.Random(f"{global_seed}_{name}")

        self.env.process(self.run())

    def _get_availability(self) -> float:
        """Get current availability based on simulation hour and outage windows."""
        window = active_window(self.env.now, self.start_hour, self.outage_windows)
        if window is not None:
            return float(window.get("availability", 0.0))
        return self.default_availability

    def _reset_second_if_needed(self):
        sec = int(self.env.now)
        if sec != self._current_second:
            self._current_second = sec
            self._second_bytes = 0

    def _congestion_delay_ms(self, flow_bytes: int) -> float:
        """Calculate remote-side congestion delay when approaching capacity."""
        if self.capacity_bps <= 0:
            return 0.0

        self._reset_second_if_needed()
        self._second_bytes += flow_bytes
        utilization = (self._second_bytes * 8) / self.capacity_bps

        if utilization < 0.7:
            return 0.0
        if utilization >= 1.0:
            return 100.0  # cap at 100ms for DC-side congestion

        frac = (utilization - 0.7) / 0.3
        return frac * frac * 100.0

    def execute(self):
        """Receive flows, apply availability and capacity constraints,
        enrich with DC metadata, and forward to sinks."""
        processing_time: float = 0.0
        data_out_list: List[Dict] = []

        while True:
            data_in = yield (0, processing_time, data_out_list)

            if data_in:
                data_out = data_in.copy()

                if data_in.get("_skip"):
                    data_out_list = [data_out]
                    processing_time = 0.0
                    continue

                self.total_flows += 1
                flow_bytes = (
                    data_in.get("orig_bytes", 0) + data_in.get("resp_bytes", 0)
                )
                self.total_bytes += flow_bytes

                # Availability check — simulate outages
                availability = self._get_availability()
                if availability < 1.0:
                    if availability <= 0.0 or self.rng.random() > availability:
                        # Flow dropped — DC endpoint is down or degraded
                        self.total_dropped += 1
                        data_out_list = []
                        processing_time = 0.0
                        if self.total_dropped <= 10 or self.total_dropped % 100 == 0:
                            print(
                                self.log_prefix(data_in["ID"])
                                + f"DC {self.label}: OUTAGE drop "
                                + f"(availability={availability:.0%}, "
                                + f"total_dropped={self.total_dropped})"
                            )
                        continue

                # Remote-side capacity constraint
                congestion_ms = self._congestion_delay_ms(flow_bytes)
                self.total_congestion_delay_ms += congestion_ms

                # Enrich flow with DC metadata
                data_out["dc_provider"] = self.provider
                data_out["dc_region"] = self.region
                data_out["dc_label"] = self.label
                data_out["dc_congestion_ms"] = round(congestion_ms, 2)

                processing_time = congestion_ms / 1000.0
                data_out_list = [data_out]

                if congestion_ms > 5.0:
                    print(
                        self.log_prefix(data_in["ID"])
                        + f"DC {self.label}: congestion "
                        + f"delay={congestion_ms:.1f}ms"
                    )
            else:
                data_out_list = []
                processing_time = 0.0
