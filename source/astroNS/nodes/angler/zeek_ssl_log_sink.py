"""
ZeekSslLogSink — writes Zeek ssl.log formatted output.

Receives flow messages and generates synthetic SSL/TLS handshake records
for flows to TLS ports (443, 993, 995, 8443). The service-catalog consumes
these to populate device_services (via SNI) and device_tls_posture (via
version, cipher, validation_status, subject, issuer).

YAML usage:
    SslLogSink:
      type: ZeekSslLogSink
      output_file: "ssl.log"
      hostname_table:
        "142.250.80.46": "www.google.com"
        "140.82.121.4": "github.com"
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

# Ports that carry TLS traffic
TLS_PORTS = {443, 993, 995, 8443}

# TLS version distribution: (version_string, weight)
TLS_VERSIONS = [
    ("TLSv13", 0.70),
    ("TLSv12", 0.25),
    ("TLSv10", 0.05),
]

# Cipher suites per TLS version
TLS_CIPHERS = {
    "TLSv13": [
        "TLS_AES_256_GCM_SHA384",
        "TLS_AES_128_GCM_SHA256",
        "TLS_CHACHA20_POLY1305_SHA256",
    ],
    "TLSv12": [
        "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
        "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
        "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
        "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
    ],
    "TLSv10": [
        "TLS_RSA_WITH_AES_128_CBC_SHA",
        "TLS_RSA_WITH_AES_256_CBC_SHA",
        "TLS_RSA_WITH_3DES_EDE_CBC_SHA",
    ],
}

# Validation status distribution: (status, weight)
VALIDATION_STATUSES = [
    ("ok", 0.95),
    ("unable to get local issuer certificate", 0.04),
    ("self signed certificate", 0.01),
]

# Certificate issuers with weights
ISSUERS = [
    ("CN=R3,O=Let's Encrypt,C=US", 0.40),
    ("CN=DigiCert SHA2 Extended Validation Server CA,OU=www.digicert.com,O=DigiCert Inc,C=US", 0.20),
    ("CN=Sectigo RSA Domain Validation Secure Server CA,O=Sectigo Limited,L=Salford,ST=Greater Manchester,C=GB", 0.15),
    ("CN=Amazon RSA 2048 M02,O=Amazon,C=US", 0.15),
    ("CN=GlobalSign Atlas R3 DV TLS CA 2024 Q1,O=GlobalSign nv-sa,C=BE", 0.10),
]


class ZeekSslLogSink(BaseNode):
    """Generates synthetic Zeek ssl.log entries from TLS flow messages."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.output_file: str = configuration.get("output_file", "ssl.log")

        output_dir = os.environ.get("ASTRONS_OUTPUT_DIR")
        if output_dir:
            self.output_file = os.path.join(output_dir, os.path.basename(self.output_file))

        # Hostname table: dst_ip -> hostname (for SNI)
        self.hostname_table: Dict[str, str] = configuration.get("hostname_table", {})

        # Deterministic RNG
        global_seed = int(configuration.get("seed", 42))
        self.rng = random.Random(f"{global_seed}_{name}")

        # Pre-compute cumulative weights for weighted random selection
        self._version_weights = self._build_cumulative([w for _, w in TLS_VERSIONS])
        self._version_values = [v for v, _ in TLS_VERSIONS]
        self._validation_weights = self._build_cumulative([w for _, w in VALIDATION_STATUSES])
        self._validation_values = [v for v, _ in VALIDATION_STATUSES]
        self._issuer_weights = self._build_cumulative([w for _, w in ISSUERS])
        self._issuer_values = [v for v, _ in ISSUERS]

        self._file: Optional[IO] = None
        self._open_file()
        self._entries_written = 0

        self.env.process(self.run())

    @staticmethod
    def _build_cumulative(weights):
        """Build cumulative weight list for weighted random selection."""
        cumulative = []
        total = 0.0
        for w in weights:
            total += w
            cumulative.append(total)
        return cumulative

    def _weighted_choice(self, values, cumulative):
        """Pick a value using pre-computed cumulative weights."""
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

    def _get_hostname(self, dst_ip: str) -> str:
        """Look up hostname for SNI field."""
        hostname = self.hostname_table.get(dst_ip)
        if hostname:
            return hostname
        octets = dst_ip.replace(".", "-")
        if dst_ip.startswith(("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                               "172.20.", "172.21.", "172.22.", "172.23.",
                               "172.24.", "172.25.", "172.26.", "172.27.",
                               "172.28.", "172.29.", "172.30.", "172.31.",
                               "192.168.")):
            return f"host-{octets}.internal.corp"
        return f"host-{octets}.external.net"

    def _write_entry(self, entry: dict):
        if self._file:
            self._file.write(json.dumps(entry) + "\n")
            self._entries_written += 1

    def execute(self):
        """Execute generator — receives flow messages, writes ssl.log for TLS ports."""
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

                if dst_port in TLS_PORTS:
                    src_ip = data_in.get("src_ip", "0.0.0.0")
                    dst_ip = data_in.get("dst_ip", "0.0.0.0")
                    flow_start = data_in.get("flow_start", 0.0)

                    uid = self._generate_uid()
                    server_name = self._get_hostname(dst_ip)
                    version = self._weighted_choice(self._version_values, self._version_weights)
                    cipher = self.rng.choice(TLS_CIPHERS[version])
                    validation = self._weighted_choice(self._validation_values, self._validation_weights)

                    # Subject: CN=<hostname>
                    subject = f"CN={server_name}"

                    # Issuer: weighted random from pool.
                    # Self-signed certs use the subject as issuer.
                    if validation == "self signed certificate":
                        issuer = subject
                    else:
                        issuer = self._weighted_choice(self._issuer_values, self._issuer_weights)

                    entry = {
                        "ts": round(flow_start, 6),
                        "_path": "ssl",
                        "uid": uid,
                        "id.orig_h": src_ip,
                        "id.orig_p": self.rng.randint(1024, 65535),
                        "id.resp_h": dst_ip,
                        "id.resp_p": dst_port,
                        "version": version,
                        "cipher": cipher,
                        "server_name": server_name,
                        "resumed": False,
                        "established": True,
                        "subject": subject,
                        "issuer": issuer,
                        "validation_status": validation,
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
