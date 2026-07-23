"""
NetworkSegment — models a network hop with latency, jitter, and optional loss.

Handles both L3 hops (routers/firewalls detected via TTL analysis) and
L2 segments (switches modeled from device count + port density).

Each segment adds per-hop latency as processing_time (2nd tuple element)
so SimPy schedules the forwarded message at the correct future time.
The 1st tuple element (delay_till_get_next_msg) is always 0 — see the
BaseNode.run() double-yield caveat in TTL-HOP-INFERENCE-PLAN.md §4b.

Congestion modeling follows SubnetAggregator's pattern: per-second byte
tracking with utilization-based queuing delay. The SimPy Store's fan-in
naturally creates contention when multiple upstream devices share one
segment.

Packet loss is modeled by yielding an empty data_out_list, which causes
BaseNode.run()'s inner loop to skip without sending output.

Time-windowed degradation enables what-if WAN scenarios: inside a
degrade window, hop latency and jitter are multiplied and loss_rate
is overridden; outside, base values apply.

YAML usage:
    Seg_10_0_1_0_24_hop3:
      type: NetworkSegment
      segment_type: router
      subnet: "IoT"
      hop_depth: 3
      hop_latency_ms: 0.8
      jitter_ms: 0.08
      loss_rate: 0.0
      devices_behind:
        - "10.0.1.30"
        - "10.0.1.31"
      SubnetAgg_IoT: ~

    WAN_to_AWS:
      type: NetworkSegment
      segment_type: wan
      subnet: "WAN"
      hop_depth: 4
      hop_latency_ms: 14.0
      jitter_ms: 2.1
      loss_rate: 0.001
      start_hour: 8
      degrade_windows:
        - start_hour: 12
          end_hour: 16
          latency_multiplier: 3.0
          loss_rate: 0.05
      DC_AWS: ~

    Switch_10_0_1_0_24_0:
      type: NetworkSegment
      segment_type: switch
      subnet: "IoT"
      hop_latency_ms: 0.005
      jitter_ms: 0.001
      loss_rate: 0.0
      port_count: 48
      uplink_ports: 4
      usable_ports: 44
      oversubscription_ratio: 1.1
      device_count: 22
      SubnetAgg_IoT: ~
"""
import random

from simpy.core import Environment
from nodes.core.base import BaseNode
from nodes.angler.hour_windows import active_window
from typing import Dict, Any, List


class NetworkSegment(BaseNode):
    """Models a network segment: adds per-hop latency, jitter, and
    optional packet loss. Supports congestion-based queuing delay
    for switch uplink oversubscription."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.segment_type: str = configuration.get("segment_type", "router")
        self.subnet: str = configuration.get("subnet", "Unknown")
        self.hop_depth: int = int(configuration.get("hop_depth", 0))

        # Latency parameters (milliseconds)
        self.hop_latency_ms: float = float(configuration.get("hop_latency_ms", 0.5))
        self.jitter_ms: float = float(configuration.get("jitter_ms", 0.0))
        self.loss_rate: float = float(configuration.get("loss_rate", 0.0))

        # What-if degrade windows: [{start_hour, end_hour,
        # latency_multiplier, loss_rate}, ...]. Empty = no windowing.
        self.degrade_windows: List[Dict] = configuration.get("degrade_windows") or []
        self.start_hour: int = int(configuration.get("start_hour", 0))

        # Switch-specific: congestion from oversubscription
        self.capacity_bps: float = float(configuration.get("capacity_bps", 0))
        self.oversubscription_ratio: float = float(
            configuration.get("oversubscription_ratio", 0)
        )
        self.port_count: int = int(configuration.get("port_count", 0))
        self.uplink_ports: int = int(configuration.get("uplink_ports", 0))

        # If no explicit capacity but we have switch params, derive it
        # uplink_ports * 10Gbps (common enterprise uplink speed)
        if self.capacity_bps <= 0 and self.uplink_ports > 0:
            self.capacity_bps = self.uplink_ports * 10_000_000_000

        # Per-second bandwidth tracking for congestion
        self._current_second: int = -1
        self._second_bytes: int = 0

        # Statistics
        self.total_flows: int = 0
        self.total_bytes: int = 0
        self.total_dropped: int = 0
        self.total_delay_ms: float = 0.0

        # Devices behind this segment (for targeted TTL decrement)
        db = configuration.get("devices_behind") or []
        self._devices_behind: set = set(db) if db else set()

        # Deterministic RNG for jitter and loss
        global_seed = int(configuration.get("seed", 42))
        self.rng = random.Random(f"{global_seed}_{name}")

        self.env.process(self.run())

    def _reset_second_if_needed(self):
        """Reset per-second counters when we enter a new second."""
        sec = int(self.env.now)
        if sec != self._current_second:
            self._current_second = sec
            self._second_bytes = 0

    def _congestion_delay_ms(self, flow_bytes: int) -> float:
        """Calculate congestion-based queuing delay for switch segments.

        Uses a simple utilization model: when instantaneous throughput
        exceeds the uplink capacity, apply quadratic delay up to a cap.
        """
        if self.capacity_bps <= 0:
            return 0.0

        self._reset_second_if_needed()
        self._second_bytes += flow_bytes
        utilization = (self._second_bytes * 8) / self.capacity_bps

        if utilization < 0.6:
            return 0.0

        if utilization >= 1.0:
            return 50.0  # cap: 50ms max congestion delay

        # Quadratic ramp from 60% to 100% utilization
        frac = (utilization - 0.6) / 0.4
        return frac * frac * 50.0

    def execute(self):
        """Execute generator — receives flow messages, applies hop latency
        and optional loss, forwards to next node."""
        processing_time: float = 0.0
        data_out_list: List[Dict] = []

        while True:
            data_in = yield (0, processing_time, data_out_list)

            if data_in:
                data_out = data_in.copy()

                # Pass through skip placeholders without latency or loss
                if data_in.get("_skip"):
                    data_out_list = [data_out]
                    processing_time = 0.0
                    continue

                self.total_flows += 1
                flow_bytes = (
                    data_in.get("orig_bytes", 0) + data_in.get("resp_bytes", 0)
                )
                self.total_bytes += flow_bytes

                # Resolve active degrade window (what-if scenarios)
                base_latency_ms = self.hop_latency_ms
                jitter_ms = self.jitter_ms
                loss_rate = self.loss_rate
                if self.degrade_windows:
                    window = active_window(
                        self.env.now, self.start_hour, self.degrade_windows
                    )
                    if window is not None:
                        mult = float(window.get("latency_multiplier", 1.0))
                        base_latency_ms *= mult
                        jitter_ms *= mult
                        if window.get("loss_rate") is not None:
                            loss_rate = float(window["loss_rate"])

                # Packet loss check
                if loss_rate > 0 and self.rng.random() < loss_rate:
                    self.total_dropped += 1
                    data_out_list = []  # dropped — empty output
                    processing_time = 0.0
                    print(
                        self.log_prefix(data_in["ID"])
                        + f"DROPPED at {self.segment_type} {self.subnet} "
                        + f"hop={self.hop_depth}"
                    )
                    continue

                # Base hop latency + jitter
                latency_ms = base_latency_ms
                if jitter_ms > 0:
                    latency_ms += self.rng.gauss(0, jitter_ms)
                    latency_ms = max(0.001, latency_ms)

                # Add congestion delay for switches with capacity limits
                congestion_ms = self._congestion_delay_ms(flow_bytes)
                latency_ms += congestion_ms
                self.total_delay_ms += latency_ms

                # Tag message with segment traversal info
                data_out["seg_latency_ms"] = round(latency_ms, 3)
                data_out["seg_type"] = self.segment_type

                # Accumulate total hop latency on the message
                prev_hop_latency = data_in.get("total_hop_latency_ms", 0.0)
                data_out["total_hop_latency_ms"] = round(
                    prev_hop_latency + latency_ms, 3
                )

                # Only TTL-inferred router segments decrement TTL.
                # Gateway and core_router are structural aggregation nodes —
                # their hops are NOT counted in the real TTL hop profiles.
                # When devices_behind is set, only decrement for those devices
                # (other devices pass through for latency but aren't at this hop depth).
                if self.segment_type == "router":
                    src_ip = data_in.get("src_ip", "")
                    if not self._devices_behind or src_ip in self._devices_behind:
                        ttl = data_in.get("ttl", 0)
                        if ttl > 0:
                            data_out["ttl"] = ttl - 1

                # Encode latency as processing_time (critical: NOT delay)
                processing_time = latency_ms / 1000.0
                data_out_list = [data_out]

                if congestion_ms > 0.1:
                    print(
                        self.log_prefix(data_in["ID"])
                        + f"{self.segment_type} {self.subnet}: "
                        + f"hop={self.hop_depth} "
                        + f"latency={latency_ms:.3f}ms "
                        + f"(congestion={congestion_ms:.1f}ms)"
                    )
            else:
                data_out_list = []
                processing_time = 0.0
