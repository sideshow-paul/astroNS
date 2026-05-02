"""
FlowRecordSink — writes flow record CSV output.

Receives fully-assembled flow messages and writes them as CSV records
matching Angler's enriched flow format. Suitable for replay into Angler
via Redis Streams injection.

YAML usage:
    FlowSink:
      type: FlowRecordSink
      output_file: "flow_records.csv"
"""
import csv
import os

from simpy.core import Environment
from nodes.core.base import BaseNode
from typing import Dict, Any, List, Optional, Callable, IO


# CSV column order matching Angler's flow record schema
FLOW_COLUMNS = [
    "flow_start",
    "flow_end",
    "src_ip",
    "src_port",
    "dst_ip",
    "dst_port",
    "protocol",
    "orig_bytes",
    "resp_bytes",
    "orig_pkts",
    "resp_pkts",
    "duration",
    "subnet",
]


class FlowRecordSink(BaseNode):
    """Writes flow messages as CSV records matching Angler's flow format."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.output_file: str = configuration.get("output_file", "flow_records.csv")

        # Allow env var to redirect output to a shared directory (k8s Job use)
        output_dir = os.environ.get("ASTRONS_OUTPUT_DIR")
        if output_dir:
            self.output_file = os.path.join(output_dir, os.path.basename(self.output_file))

        # Deterministic RNG for source port generation
        import random
        global_seed = int(configuration.get("seed", 42))
        self.rng = random.Random(f"{global_seed}_{name}")

        self._file: Optional[IO] = None
        self._writer: Optional[csv.DictWriter] = None
        self._open_file()

        self.env.process(self.run())

    def _open_file(self):
        """Open the CSV file and write the header."""
        os.makedirs(os.path.dirname(self.output_file) or ".", exist_ok=True)
        self._file = open(self.output_file, "w", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=FLOW_COLUMNS)
        self._writer.writeheader()

    def execute(self):
        """Execute generator — receives flow messages, writes CSV."""
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

                flow_start = data_in.get("flow_start", 0.0)
                duration = data_in.get("duration", 0.0) or 0.0
                flow_end = flow_start + duration
                src_port = self.rng.randint(1024, 65535)

                row = {
                    "flow_start": f"{flow_start:.6f}",
                    "flow_end": f"{flow_end:.6f}",
                    "src_ip": data_in.get("src_ip", "0.0.0.0"),
                    "src_port": src_port,
                    "dst_ip": data_in.get("dst_ip", "0.0.0.0"),
                    "dst_port": data_in.get("dst_port", 0),
                    "protocol": data_in.get("protocol", "tcp"),
                    "orig_bytes": data_in.get("orig_bytes", 0),
                    "resp_bytes": data_in.get("resp_bytes", 0),
                    "orig_pkts": data_in.get("orig_pkts", 0),
                    "resp_pkts": data_in.get("resp_pkts", 0),
                    "duration": f"{duration:.6f}",
                    "subnet": data_in.get("subnet", ""),
                }

                if self._writer:
                    self._writer.writerow(row)

                processing_time = 0.0
                data_out_list = [data_in.copy()]

                print(
                    self.log_prefix(data_in["ID"])
                    + f"flow.csv: {row['src_ip']}:{src_port} -> "
                    + f"{row['dst_ip']}:{row['dst_port']} "
                    + f"bytes={row['orig_bytes']}/{row['resp_bytes']}"
                )
            else:
                data_out_list = []
                processing_time = 0.0

    def __del__(self):
        if self._file and not self._file.closed:
            self._file.close()
