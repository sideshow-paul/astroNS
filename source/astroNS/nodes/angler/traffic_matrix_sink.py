"""
TrafficMatrixSink — accumulates a subnet-to-subnet traffic matrix.

Receives flow messages and classifies each (src_subnet, dst_subnet) pair,
accumulating total bytes and flow counts. At simulation end, writes a CSV
matrix and a human-readable summary.

Each destination IP is classified by checking against configured subnet
CIDRs. If no subnet matches, the destination is classified as "Internet".

YAML usage:
    MatrixSink:
      type: TrafficMatrixSink
      output_file: "traffic_matrix.csv"
      subnet_cidrs:
        Engineering_HQ: "10.1.1.0/24"
        IoT_HQ: "10.1.2.0/24"
        WiFi_HQ: "10.1.3.0/24"
"""
import atexit
import csv
import os
from collections import defaultdict

from simpy.core import Environment
from nodes.core.base import BaseNode
from typing import Dict, Any, List, Optional, Tuple, IO


def _parse_cidr(cidr: str) -> Tuple[int, int]:
    """Parse CIDR string to (network_int, broadcast_int) inclusive range."""
    parts = cidr.split("/")
    ip_str = parts[0]
    prefix_len = int(parts[1]) if len(parts) > 1 else 24

    octets = ip_str.split(".")
    ip_int = (
        (int(octets[0]) << 24)
        | (int(octets[1]) << 16)
        | (int(octets[2]) << 8)
        | int(octets[3])
    )

    host_bits = 32 - prefix_len
    network = ip_int & (0xFFFFFFFF << host_bits)
    broadcast = network | ((1 << host_bits) - 1)
    return network, broadcast


def _ip_to_int(ip_str: str) -> int:
    """Convert dotted-quad IP string to 32-bit integer."""
    octets = ip_str.split(".")
    return (
        (int(octets[0]) << 24)
        | (int(octets[1]) << 16)
        | (int(octets[2]) << 8)
        | int(octets[3])
    )


def _format_bytes(n: float) -> str:
    """Format byte count with human-readable suffix."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


class TrafficMatrixSink(BaseNode):
    """Accumulates a (src_subnet, dst_subnet|Internet) traffic matrix."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.output_file: str = configuration.get(
            "output_file", "traffic_matrix.csv"
        )

        output_dir = os.environ.get("ASTRONS_OUTPUT_DIR")
        if output_dir:
            self.output_file = os.path.join(
                output_dir, os.path.basename(self.output_file)
            )

        # Parse subnet CIDRs once: {subnet_name: (network_int, broadcast_int)}
        raw_cidrs = configuration.get("subnet_cidrs", {})
        self._subnet_ranges: List[Tuple[str, int, int]] = []
        for subnet_name, cidr in raw_cidrs.items():
            net, bcast = _parse_cidr(cidr)
            self._subnet_ranges.append((subnet_name, net, bcast))

        # Matrix: (src_subnet, dst_subnet) → {bytes, flows}
        self.matrix: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(
            lambda: {"bytes": 0, "flows": 0}
        )

        # Track all subnet names seen (for column ordering)
        self._all_subnets: set = set(raw_cidrs.keys())

        # Write output on interpreter exit (sim end)
        atexit.register(self._write_output)

        self.env.process(self.run())

    def _classify_ip(self, ip_str: str) -> str:
        """Classify an IP into a subnet name or 'Internet'."""
        try:
            ip_int = _ip_to_int(ip_str)
        except (ValueError, IndexError):
            return "Internet"

        for subnet_name, net, bcast in self._subnet_ranges:
            if net <= ip_int <= bcast:
                return subnet_name
        return "Internet"

    def execute(self):
        """Execute generator — receives flow messages, accumulates matrix."""
        processing_time: float = 0.0
        data_out_list: List[Dict] = []

        while True:
            data_in = yield (0, processing_time, data_out_list)

            if data_in:
                if data_in.get("_skip"):
                    data_out_list = [data_in.copy()]
                    processing_time = 0.0
                    continue

                src_subnet = data_in.get("subnet", "Unknown")
                dst_ip = data_in.get("dst_ip", "0.0.0.0")
                dst_subnet = self._classify_ip(dst_ip)

                orig_bytes = int(data_in.get("orig_bytes", 0))
                resp_bytes = int(data_in.get("resp_bytes", 0))
                total_bytes = orig_bytes + resp_bytes

                self._all_subnets.add(src_subnet)
                if dst_subnet != "Internet":
                    self._all_subnets.add(dst_subnet)

                cell = self.matrix[(src_subnet, dst_subnet)]
                cell["bytes"] += total_bytes
                cell["flows"] += 1

                processing_time = 0.0
                data_out_list = [data_in.copy()]
            else:
                data_out_list = []
                processing_time = 0.0

    def _write_output(self):
        """Write CSV and summary matrix to output file."""
        if not self.matrix:
            return

        os.makedirs(os.path.dirname(self.output_file) or ".", exist_ok=True)

        # CSV output: one row per (src, dst) pair with non-zero traffic
        with open(self.output_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "src_subnet",
                    "dst_subnet",
                    "total_bytes",
                    "total_flows",
                    "mean_bytes_per_flow",
                ]
            )
            for (src, dst), cell in sorted(self.matrix.items()):
                mean = cell["bytes"] / cell["flows"] if cell["flows"] > 0 else 0
                writer.writerow(
                    [src, dst, cell["bytes"], cell["flows"], f"{mean:.0f}"]
                )

        # Human-readable summary alongside the CSV
        summary_file = self.output_file.rsplit(".", 1)[0] + "_summary.txt"
        self._write_summary(summary_file)

    def _write_summary(self, summary_file: str):
        """Write a fixed-width matrix summary."""
        # Column order: sorted subnet names + Internet last
        subnets_sorted = sorted(self._all_subnets)
        columns = subnets_sorted + ["Internet"]

        # Row order: same as columns (minus Internet as source, unless present)
        row_subnets = sorted(
            set(src for src, _ in self.matrix.keys())
        )

        # Column width
        col_w = max(14, max((len(c) for c in columns), default=14) + 2)
        label_w = max(14, max((len(r) for r in row_subnets), default=14) + 2)

        with open(summary_file, "w") as f:
            f.write("Traffic Matrix Summary\n")
            f.write("=" * (label_w + col_w * len(columns)) + "\n\n")

            # Header row
            f.write(" " * label_w)
            for col in columns:
                f.write(col.rjust(col_w))
            f.write("\n")

            # Data rows
            for src in row_subnets:
                f.write(src.ljust(label_w))
                for dst in columns:
                    cell = self.matrix.get((src, dst))
                    if cell and cell["flows"] > 0:
                        f.write(_format_bytes(cell["bytes"]).rjust(col_w))
                    else:
                        f.write("-".rjust(col_w))
                f.write("\n")

            # Totals
            f.write("\n")
            total_flows = sum(c["flows"] for c in self.matrix.values())
            total_bytes = sum(c["bytes"] for c in self.matrix.values())
            f.write(f"Total flows: {total_flows:,}\n")
            f.write(f"Total bytes: {_format_bytes(total_bytes)}\n")
            f.write(f"Unique pairs: {len(self.matrix)}\n")

    def __del__(self):
        # atexit handles writing; nothing else to clean up
        pass
