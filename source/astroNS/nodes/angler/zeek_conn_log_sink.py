"""
ZeekConnLogSink — writes Zeek conn.log formatted output.

Receives fully-assembled flow messages and writes them as Zeek conn.log
JSON entries. Each line is a valid JSON object matching the Zeek conn.log
schema, suitable for replay into Angler via NATS.

YAML usage:
    ConnLogSink:
      type: ZeekConnLogSink
      output_file: "conn.log"
"""
import json
import os
import random
import string

from simpy.core import Environment
from nodes.core.base import BaseNode
from typing import Dict, Any, List, Optional, Callable, IO


# Zeek uid charset (base62-like)
ZEEK_UID_CHARS = string.ascii_letters + string.digits


class ZeekConnLogSink(BaseNode):
    """Formats flow messages as Zeek conn.log JSON entries and writes
    them to a file."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.output_file: str = configuration.get("output_file", "conn.log")

        # Allow env var to redirect output to a shared directory (k8s Job use)
        output_dir = os.environ.get("ASTRONS_OUTPUT_DIR")
        if output_dir:
            self.output_file = os.path.join(output_dir, os.path.basename(self.output_file))

        # Deterministic RNG for uid generation
        global_seed = int(configuration.get("seed", 42))
        self.rng = random.Random(f"{global_seed}_{name}")

        self._file: Optional[IO] = None
        self._open_file()

        self.env.process(self.run())

    def _open_file(self):
        """Open the output file for writing."""
        os.makedirs(os.path.dirname(self.output_file) or ".", exist_ok=True)
        self._file = open(self.output_file, "w")

    def _generate_uid(self) -> str:
        """Generate a Zeek-style connection uid."""
        return "C" + "".join(
            self.rng.choice(ZEEK_UID_CHARS) for _ in range(17)
        )

    def _protocol_to_zeek(self, protocol) -> str:
        """Normalize protocol (string or IANA number) for Zeek."""
        if isinstance(protocol, int):
            return {1: "icmp", 6: "tcp", 17: "udp"}.get(protocol, "tcp")
        p = str(protocol).lower() if protocol else "tcp"
        if p in ("tcp", "udp", "icmp"):
            return p
        return "tcp"

    def _conn_state(self, protocol: str, duration: float) -> str:
        """Generate a plausible Zeek connection state."""
        if protocol == "udp":
            return "SF" if duration > 0 else "S0"
        if duration > 0.1:
            return "SF"   # Normal completion
        if duration > 0:
            return "S1"   # Connection established, no reply close
        return "S0"       # SYN only

    def _history(self, protocol: str, duration: float) -> str:
        """Generate a plausible Zeek connection history string."""
        if protocol == "udp":
            return "Dd"
        if duration > 0.1:
            return "ShADadFf"
        if duration > 0:
            return "ShADad"
        return "S"

    def execute(self):
        """Execute generator — receives flow messages, writes conn.log."""
        processing_time: float = 0.0
        data_out_list: List[Dict] = []

        while True:
            data_in = yield (0, processing_time, data_out_list)

            if data_in:
                # Skip placeholders
                if data_in.get("_skip"):
                    data_out_list = [data_in.copy()]
                    processing_time = 0.0
                    continue

                uid = self._generate_uid()
                protocol = self._protocol_to_zeek(data_in.get("protocol", "tcp"))
                duration = data_in.get("duration", 0.0) or 0.0
                orig_bytes = data_in.get("orig_bytes", 0)
                resp_bytes = data_in.get("resp_bytes", 0)
                orig_pkts = data_in.get("orig_pkts", 0)
                resp_pkts = data_in.get("resp_pkts", 0)
                src_port = self.rng.randint(1024, 65535)

                # QoS delay shifts flow_start forward (queuing adds latency)
                qos_delay_ms = data_in.get("qos_delay_ms", 0.0) or 0.0
                qos_delay_sec = qos_delay_ms / 1000.0
                flow_start = data_in.get("flow_start", 0.0) + qos_delay_sec

                conn_entry = {
                    "ts": flow_start,
                    "uid": uid,
                    "id.orig_h": data_in.get("src_ip", "0.0.0.0"),
                    "id.orig_p": src_port,
                    "id.resp_h": data_in.get("dst_ip", "0.0.0.0"),
                    "id.resp_p": data_in.get("dst_port", 0),
                    "proto": protocol,
                    "service": self._guess_service(
                        data_in.get("dst_port", 0), protocol
                    ),
                    "duration": round(duration, 6),
                    "orig_bytes": orig_bytes,
                    "resp_bytes": resp_bytes,
                    "conn_state": self._conn_state(protocol, duration),
                    "local_orig": True,
                    "local_resp": False,
                    "missed_bytes": 0,
                    "history": self._history(protocol, duration),
                    "orig_pkts": orig_pkts,
                    "orig_ip_bytes": orig_bytes + (orig_pkts * 40),
                    "resp_pkts": resp_pkts,
                    "resp_ip_bytes": resp_bytes + (resp_pkts * 40),
                    "_path": "conn",
                }

                # Include TCP handshake duration when present (RTT in seconds).
                # For TCP flows, queuing delay (from SubnetAggregator) inflates
                # the SYN-ACK round-trip, so we add it to the base RTT.
                tcp_hs_ms = data_in.get("tcp_handshake_ms")
                if tcp_hs_ms is not None and tcp_hs_ms > 0:
                    if protocol == "tcp" and qos_delay_ms > 0:
                        tcp_hs_ms = tcp_hs_ms + qos_delay_ms
                    conn_entry["tcp_handshake_duration"] = round(tcp_hs_ms / 1000.0, 6)

                # Include QoS metadata when present
                qos_class = data_in.get("qos_class")
                if qos_class:
                    conn_entry["qos_class"] = qos_class
                if qos_delay_ms > 0:
                    conn_entry["qos_delay_ms"] = round(qos_delay_ms, 2)

                if self._file:
                    self._file.write(json.dumps(conn_entry) + "\n")

                processing_time = 0.0
                data_out_list = [data_in.copy()]

                print(
                    self.log_prefix(data_in["ID"])
                    + f"conn.log: {uid} {conn_entry['id.orig_h']}:{src_port} -> "
                    + f"{conn_entry['id.resp_h']}:{conn_entry['id.resp_p']}"
                )
            else:
                data_out_list = []
                processing_time = 0.0

    @staticmethod
    def _guess_service(port: int, protocol: str) -> Optional[str]:
        """Guess the Zeek service name from port/protocol."""
        services = {
            (53, "udp"): "dns",
            (53, "tcp"): "dns",
            (80, "tcp"): "http",
            (443, "tcp"): "ssl",
            (22, "tcp"): "ssh",
            (25, "tcp"): "smtp",
            (110, "tcp"): "pop3",
            (143, "tcp"): "imap",
            (993, "tcp"): "ssl",
            (995, "tcp"): "ssl",
            (8080, "tcp"): "http",
            (8443, "tcp"): "ssl",
            (123, "udp"): "ntp",
        }
        return services.get((port, protocol))

    def __del__(self):
        if self._file and not self._file.closed:
            self._file.close()
