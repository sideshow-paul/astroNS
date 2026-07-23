"""
SiteGateway — site-level traffic aggregator with provider classification
and ISP uplink bandwidth constraint.

Receives flows from SubnetAggregators, classifies each destination IP
into a cloud provider, enriches the flow with ``dc_provider``, and
forwards to per-provider WAN links via predicate routing on that field.

The uplink bandwidth constraint models a shared ISP link: when total
site throughput exceeds ``uplink_capacity_bps``, QoS-aware queuing
delay is applied (same M/M/1 model as SubnetAggregator).

Provider classification uses IP prefix matching against the same
prefix lists used by ``sim-fleet/rtt_histogram.py``.

Time-windowed capacity constraints enable what-if uplink scenarios
(e.g. ISP reroute through a backup path): inside a constraint window
the window's ``capacity_bps`` replaces ``uplink_capacity_bps``.

YAML usage:
    SiteGateway_TX:
      type: SiteGateway
      site_id: angler-tx
      uplink_capacity_bps: 1000000000
      constraint_windows:
        - start_hour: 13
          end_hour: 16
          capacity_bps: 100000000
      provider_prefixes:
        AWS: ["3.", "13.", "15.", "34.", "52.", "54."]
        Google: ["8.8.", "64.233", "142.250", "172.217"]
        Azure: ["20.", "40.", "51.", "104.40"]
        CDN: ["104.16", "104.17", "23.2"]
      WAN_to_AWS: "dc_provider == AWS"
      WAN_to_Google: "dc_provider == Google"
      WAN_to_Other: "dc_provider == Other"
"""
from simpy.core import Environment
from nodes.core.base import BaseNode
from nodes.angler.hour_windows import active_window
from typing import Dict, Any, List, Optional
from collections import defaultdict


class SiteGateway(BaseNode):
    """Site-level gateway: classifies traffic by cloud provider,
    enforces ISP uplink bandwidth, and fans out to per-provider
    WAN links."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.site_id: str = configuration.get("site_id", "unknown")
        self.uplink_capacity_bps: float = float(
            configuration.get("uplink_capacity_bps", 1_000_000_000)
        )

        # What-if constraint windows: [{start_hour, end_hour,
        # capacity_bps}, ...]. Empty = constant capacity.
        self.constraint_windows: List[Dict] = (
            configuration.get("constraint_windows") or []
        )

        # Build provider prefix lookup from configuration.
        # provider_prefixes: {provider_name: [prefix_str, ...]}
        raw_prefixes = configuration.get("provider_prefixes") or {}
        # Build a flat list of (prefix, provider) sorted longest-first
        # for correct matching (e.g., "104.16" before "104.").
        self._prefix_table: List[tuple] = []
        for provider, prefixes in raw_prefixes.items():
            for prefix in prefixes:
                self._prefix_table.append((prefix, provider))
        self._prefix_table.sort(key=lambda x: -len(x[0]))

        self.default_provider: str = configuration.get("default_provider", "Other")

        # Bandwidth tracking
        self.total_bytes: int = 0
        self.total_flows: int = 0
        self._current_second: int = -1
        self._second_bytes: int = 0

        # Provider statistics
        self.provider_flows: Dict[str, int] = defaultdict(int)
        self.provider_bytes: Dict[str, int] = defaultdict(int)

        # QoS parameters (same as SubnetAggregator)
        self.day_type: str = configuration.get("day_type", "BIZ")
        self.start_hour: int = int(configuration.get("start_hour", 0))

        self.env.process(self.run())

    def _classify_provider(self, ip: str) -> str:
        """Classify a destination IP into a cloud provider by prefix match."""
        for prefix, provider in self._prefix_table:
            if ip.startswith(prefix):
                return provider
        return self.default_provider

    def _reset_second_if_needed(self):
        sec = int(self.env.now)
        if sec != self._current_second:
            self._current_second = sec
            self._second_bytes = 0

    # QoS delay parameters — lighter than SubnetAggregator since the
    # gateway is a single choke point, not a per-subnet enforcer.
    _QOS_PARAMS = {
        "EF": {"service_time_ms": 0.3,  "max_delay_ms": 5.0,   "onset": 0.85},
        "AF": {"service_time_ms": 0.8,  "max_delay_ms": 100.0,  "onset": 0.50},
        "BE": {"service_time_ms": 1.5,  "max_delay_ms": 500.0, "onset": 0.30},
    }

    def _current_capacity_bps(self) -> float:
        """Effective uplink capacity, honoring any active constraint window."""
        if self.constraint_windows:
            window = active_window(
                self.env.now, self.start_hour, self.constraint_windows
            )
            if window is not None:
                return float(window.get("capacity_bps", self.uplink_capacity_bps))
        return self.uplink_capacity_bps

    def _calculate_uplink_delay(self, flow_bytes: int, qos_class: str) -> float:
        """Calculate ISP uplink queuing delay using M/M/1 approximation."""
        capacity_bps = self._current_capacity_bps()
        if capacity_bps <= 0:
            return 0.0

        params = self._QOS_PARAMS.get(qos_class, self._QOS_PARAMS["BE"])

        self._reset_second_if_needed()
        self._second_bytes += flow_bytes
        rho = (self._second_bytes * 8) / capacity_bps

        if rho < params["onset"]:
            return 0.0
        if rho >= 1.0:
            return params["max_delay_ms"]

        effective_rho = (rho - params["onset"]) / (1.0 - params["onset"])
        delay = params["service_time_ms"] * effective_rho / (1.0 - effective_rho)
        return min(delay, params["max_delay_ms"])

    def execute(self):
        """Receive flows, classify provider, enforce uplink bandwidth,
        forward with dc_provider tag for predicate routing."""
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

                # Classify destination into a cloud provider
                dst_ip = data_in.get("dst_ip", "")
                provider = self._classify_provider(dst_ip)
                data_out["dc_provider"] = provider

                self.provider_flows[provider] += 1
                self.provider_bytes[provider] += flow_bytes

                # ISP uplink bandwidth constraint
                qos_class = data_in.get("qos_class", "BE")
                if qos_class not in ("EF", "AF", "BE"):
                    qos_class = "BE"

                uplink_delay_ms = self._calculate_uplink_delay(flow_bytes, qos_class)
                data_out["uplink_delay_ms"] = round(uplink_delay_ms, 2)

                processing_time = uplink_delay_ms / 1000.0
                data_out_list = [data_out]

                if uplink_delay_ms > 1.0:
                    print(
                        self.log_prefix(data_in["ID"])
                        + f"Gateway {self.site_id}: uplink congestion "
                        + f"delay={uplink_delay_ms:.1f}ms "
                        + f"provider={provider} qos={qos_class}"
                    )
            else:
                data_out_list = []
                processing_time = 0.0
