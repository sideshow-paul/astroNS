"""
ZeekHttpLogSink — writes Zeek http.log formatted output.

Receives flow messages and generates synthetic HTTP request/response records
for flows to HTTP ports (80, 8080). The service-catalog consumes these to
populate device_services (via Host header) and device_user_agents (via
User-Agent header).

Most modern traffic is HTTPS (port 443 → ssl.log), so http.log is
relatively sparse — which is realistic.

YAML usage:
    HttpLogSink:
      type: ZeekHttpLogSink
      output_file: "http.log"
      hostname_table:
        "169.254.169.254": "metadata.internal"
"""
import json
import os
import random
import string

from simpy.core import Environment
from nodes.core.base import BaseNode
from typing import Dict, Any, List, Optional, IO


# Zeek uid charset (base62-like)
ZEEK_UID_CHARS = string.ascii_letters + string.digits

# Ports that carry HTTP traffic
HTTP_PORTS = {80, 8080}

# HTTP methods with weights
HTTP_METHODS = [
    ("GET", 0.70),
    ("POST", 0.20),
    ("PUT", 0.05),
    ("DELETE", 0.05),
]

# Status codes with weights
HTTP_STATUS_CODES = [
    (200, "OK", 0.85),
    (301, "Moved Permanently", 0.05),
    (404, "Not Found", 0.05),
    (500, "Internal Server Error", 0.03),
    (403, "Forbidden", 0.02),
]

# URI paths by category
URI_PATHS = [
    "/",
    "/api/v1/data",
    "/api/v1/status",
    "/api/v2/query",
    "/health",
    "/healthz",
    "/metrics",
    "/latest/meta-data/",
    "/latest/meta-data/instance-id",
    "/favicon.ico",
    "/robots.txt",
    "/login",
    "/dashboard",
    "/assets/main.js",
    "/assets/style.css",
    "/images/logo.png",
]

# User-Agent strings per platform
USER_AGENTS = [
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36", 0.30),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36", 0.15),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36", 0.10),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0", 0.10),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15", 0.08),
    ("python-requests/2.31.0", 0.08),
    ("curl/8.7.1", 0.07),
    ("Go-http-client/2.0", 0.05),
    ("axios/1.6.8", 0.04),
    ("Wget/1.21.4", 0.03),
]


class ZeekHttpLogSink(BaseNode):
    """Generates synthetic Zeek http.log entries from HTTP flow messages."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.output_file: str = configuration.get("output_file", "http.log")

        output_dir = os.environ.get("ASTRONS_OUTPUT_DIR")
        if output_dir:
            self.output_file = os.path.join(output_dir, os.path.basename(self.output_file))

        # Hostname table: dst_ip -> hostname (for Host header)
        self.hostname_table: Dict[str, str] = configuration.get("hostname_table", {})

        # Deterministic RNG
        global_seed = int(configuration.get("seed", 42))
        self.rng = random.Random(f"{global_seed}_{name}")

        # Pre-compute cumulative weights
        self._method_weights = self._build_cumulative([w for _, w in HTTP_METHODS])
        self._method_values = [v for v, _ in HTTP_METHODS]
        self._status_weights = self._build_cumulative([w for _, _, w in HTTP_STATUS_CODES])
        self._status_values = [(c, m) for c, m, _ in HTTP_STATUS_CODES]
        self._ua_weights = self._build_cumulative([w for _, w in USER_AGENTS])
        self._ua_values = [v for v, _ in USER_AGENTS]

        self._file: Optional[IO] = None
        self._open_file()
        self._entries_written = 0

        self.env.process(self.run())

    @staticmethod
    def _build_cumulative(weights):
        cumulative = []
        total = 0.0
        for w in weights:
            total += w
            cumulative.append(total)
        return cumulative

    def _weighted_choice(self, values, cumulative):
        r = self.rng.random()
        for i, threshold in enumerate(cumulative):
            if r < threshold:
                return values[i]
        return values[-1]

    def _open_file(self):
        os.makedirs(os.path.dirname(self.output_file) or ".", exist_ok=True)
        self._file = open(self.output_file, "w")

    def _generate_uid(self) -> str:
        return "C" + "".join(
            self.rng.choice(ZEEK_UID_CHARS) for _ in range(17)
        )

    def _get_hostname(self, dst_ip: str, dst_port: int) -> str:
        """Build Host header value from hostname table."""
        hostname = self.hostname_table.get(dst_ip)
        if not hostname:
            octets = dst_ip.replace(".", "-")
            if dst_ip.startswith(("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                                   "172.20.", "172.21.", "172.22.", "172.23.",
                                   "172.24.", "172.25.", "172.26.", "172.27.",
                                   "172.28.", "172.29.", "172.30.", "172.31.",
                                   "192.168.")):
                hostname = f"host-{octets}.internal.corp"
            else:
                hostname = f"host-{octets}.external.net"
        # Include port in Host header for non-standard ports
        if dst_port != 80:
            return f"{hostname}:{dst_port}"
        return hostname

    def _write_entry(self, entry: dict):
        if self._file:
            self._file.write(json.dumps(entry) + "\n")
            self._entries_written += 1

    def execute(self):
        """Execute generator — receives flow messages, writes http.log for HTTP ports."""
        processing_time: float = 0.0
        data_out_list: List[Dict] = []

        while True:
            data_in = yield (0, processing_time, data_out_list)

            if data_in:
                if data_in.get("_skip"):
                    data_out_list = [data_in.copy()]
                    processing_time = 0.0
                    continue

                dst_port = data_in.get("dst_port", 0)

                if dst_port in HTTP_PORTS:
                    src_ip = data_in.get("src_ip", "0.0.0.0")
                    dst_ip = data_in.get("dst_ip", "0.0.0.0")
                    flow_start = data_in.get("flow_start", 0.0)
                    orig_bytes = data_in.get("orig_bytes", 0)
                    resp_bytes = data_in.get("resp_bytes", 0)

                    uid = self._generate_uid()
                    method = self._weighted_choice(self._method_values, self._method_weights)
                    status_code, status_msg = self._weighted_choice(self._status_values, self._status_weights)
                    host = self._get_hostname(dst_ip, dst_port)
                    uri = self.rng.choice(URI_PATHS)
                    user_agent = self._weighted_choice(self._ua_values, self._ua_weights)

                    entry = {
                        "ts": round(flow_start, 6),
                        "_path": "http",
                        "uid": uid,
                        "id.orig_h": src_ip,
                        "id.orig_p": self.rng.randint(1024, 65535),
                        "id.resp_h": dst_ip,
                        "id.resp_p": dst_port,
                        "method": method,
                        "host": host,
                        "uri": uri,
                        "user_agent": user_agent,
                        "status_code": status_code,
                        "status_msg": status_msg,
                        "request_body_len": orig_bytes,
                        "response_body_len": resp_bytes,
                    }

                    self._write_entry(entry)

                processing_time = 0.0
                data_out_list = [data_in.copy()]
            else:
                data_out_list = []
                processing_time = 0.0

    def __del__(self):
        if self._file and not self._file.closed:
            self._file.close()
