"""
SubnetAggregator — tracks per-subnet bandwidth and forwards to sinks.

Receives fully-assembled flow messages and tracks cumulative bandwidth
per subnet with QoS-aware bandwidth enforcement. Passes all messages
through to connected output sinks (ZeekConnLogSink, FlowRecordSink).

QoS classes (DiffServ):
  EF — Expedited Forwarding: priority queue, zero queuing delay
  AF — Assured Forwarding: guaranteed bandwidth share, moderate delay under congestion
  BE — Best Effort: no guarantees, highest delay under congestion

When total subnet throughput exceeds max_bps for the current hour,
queuing delays are applied based on QoS class priority.

YAML usage:
    SubnetAgg_IoT:
      type: SubnetAggregator
      subnet_name: "IoT"
      subnet_cidr: "10.0.1.0/24"
      latitude: 38.8882      # optional, for Angler map placement
      longitude: -77.0199    # optional, for Angler map placement
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
    """Tracks per-subnet bandwidth usage with QoS-aware enforcement
    and forwards flow messages to output sinks."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.subnet_name: str = configuration.get("subnet_name", "Unknown")
        self.subnet_cidr: str = configuration.get("subnet_cidr", "0.0.0.0/0")
        self.latitude: Optional[float] = configuration.get("latitude")
        self.longitude: Optional[float] = configuration.get("longitude")
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

        # Per-second bandwidth tracking for QoS enforcement
        self._current_second: int = -1
        self._second_bytes: int = 0
        self._second_bytes_ef: int = 0
        self._second_bytes_af: int = 0
        self._second_bytes_be: int = 0

        # QoS statistics
        self.qos_stats: Dict[str, int] = {"EF": 0, "AF": 0, "BE": 0}
        self.total_qos_delay_ms: float = 0.0

        self.env.process(self.run())

    def _get_second(self) -> int:
        """Current simulation second."""
        return int(self.env.now)

    def _reset_second_if_needed(self):
        """Reset per-second counters when we enter a new second."""
        sec = self._get_second()
        if sec != self._current_second:
            self._current_second = sec
            self._second_bytes = 0
            self._second_bytes_ef = 0
            self._second_bytes_af = 0
            self._second_bytes_be = 0

    def _calculate_qos_delay(self, flow_bytes: int, qos_class: str,
                              max_bps: float) -> float:
        """Calculate queuing delay in milliseconds based on QoS class
        and current bandwidth utilization.

        Returns delay in ms:
          EF: 0 ms (priority, always passes)
          AF: 0-50 ms proportional to congestion
          BE: 0-200 ms proportional to congestion, increases sharply near max
        """
        if max_bps <= 0:
            return 0.0

        # Current utilization as fraction of max (bits per second)
        current_bps = self._second_bytes * 8
        utilization = current_bps / max_bps

        if qos_class == "EF":
            # Priority: zero queuing delay regardless of utilization
            return 0.0
        elif qos_class == "AF":
            # Assured: small delay only when utilization > 80%
            if utilization < 0.8:
                return 0.0
            # Linear ramp: 0ms at 80% → 50ms at 100%+
            congestion = min(2.0, (utilization - 0.8) / 0.2)
            return congestion * 25.0
        else:
            # Best Effort: delay ramps from 60% utilization
            if utilization < 0.6:
                return 0.0
            # Quadratic ramp: 0ms at 60% → 200ms at 100%+
            congestion = min(2.0, (utilization - 0.6) / 0.4)
            return congestion * congestion * 50.0

    def execute(self):
        """Execute generator — receives flow messages, tracks bandwidth
        with QoS enforcement, and forwards to sinks."""
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

                    # QoS class from upstream (WeightedDestSelector)
                    qos_class = data_in.get("qos_class", "BE")
                    if qos_class not in ("EF", "AF", "BE"):
                        qos_class = "BE"
                    self.qos_stats[qos_class] += 1

                    # Per-second bandwidth tracking
                    self._reset_second_if_needed()
                    self._second_bytes += flow_bytes
                    if qos_class == "EF":
                        self._second_bytes_ef += flow_bytes
                    elif qos_class == "AF":
                        self._second_bytes_af += flow_bytes
                    else:
                        self._second_bytes_be += flow_bytes

                    # QoS-aware bandwidth enforcement
                    bw_key = f"{self.day_type}_{hour}"
                    bw_profile = self.bw_profiles.get(bw_key)
                    max_bps = 0.0
                    qos_delay_ms = 0.0

                    if bw_profile and flow_bytes > 0:
                        max_bps = bw_profile.get("max_bps", 0) or 0.0

                        if max_bps > 0:
                            # Calculate QoS-aware queuing delay
                            qos_delay_ms = self._calculate_qos_delay(
                                flow_bytes, qos_class, max_bps
                            )
                            self.total_qos_delay_ms += qos_delay_ms

                            # Log bandwidth warnings
                            duration = data_in.get("duration", 1.0) or 1.0
                            flow_bps = (flow_bytes * 8) / duration
                            if flow_bps > max_bps:
                                print(
                                    self.log_prefix(data_in["ID"])
                                    + f"BW WARNING: {self.subnet_name} flow "
                                    + f"{flow_bps:.0f} bps > max {max_bps:.0f} bps"
                                    + f" [qos={qos_class}]"
                                )

                    # Tag the message with subnet info and QoS metrics
                    data_out["agg_subnet"] = self.subnet_name
                    data_out["agg_total_flows"] = self.total_flows
                    data_out["qos_class"] = qos_class
                    data_out["qos_delay_ms"] = round(qos_delay_ms, 2)

                # Inject QoS delay into SimPy timeline so congestion
                # creates real backpressure on upstream flow generation.
                processing_time = qos_delay_ms / 1000.0
                data_out_list = [data_out]

                if not data_in.get("_skip"):
                    qos_info = f" qos={data_out.get('qos_class', 'BE')}"
                    delay = data_out.get("qos_delay_ms", 0)
                    if delay > 0:
                        qos_info += f" delay={delay:.1f}ms"
                    print(
                        self.log_prefix(data_in["ID"])
                        + f"Subnet {self.subnet_name}: flow #{self.total_flows} "
                        + f"total_bytes={self.total_bytes}"
                        + qos_info
                    )
            else:
                data_out_list = []
                processing_time = 0.0
