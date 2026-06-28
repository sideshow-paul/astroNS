"""
ZeekDnsLogSink — writes Zeek dns.log formatted output.

Receives fully-assembled flow messages and generates synthetic DNS query
records. For each flow, a DNS lookup is implied: the client resolved the
destination hostname before connecting.

Two modes per flow:
  - Port-53 flows: the flow IS a DNS query. Pick a random hostname from
    the hostname table as the query, return the mapped IP as the answer.
  - Non-port-53 flows: generate a DNS entry representing the lookup that
    preceded this connection. Look up dst_ip in hostname_table to get the
    query name, return dst_ip as the answer.

DNS caching: tracks (src_ip, hostname) pairs and only generates a new DNS
entry when the TTL (default 300s) has expired, mimicking resolver caching.

A small fraction of queries (configurable) are DGA-like NXDOMAIN responses
to trigger the dns-detector's anomaly detection.

YAML usage:
    DnsLogSink:
      type: ZeekDnsLogSink
      output_file: "dns.log"
      hostname_table:
        "142.250.80.46": "www.google.com"
        "8.8.8.8": "dns.google"
      dns_resolver: "8.8.8.8"
      dga_rate: 0.02
"""
import json
import math
import os
import random
import string

from simpy.core import Environment
from nodes.core.base import BaseNode
from typing import Dict, Any, List, Optional, IO


# Zeek uid charset (base62-like)
ZEEK_UID_CHARS = string.ascii_letters + string.digits

# Common TLDs for DGA generation
DGA_TLDS = [".com", ".net", ".org", ".info", ".xyz", ".top", ".biz"]


class ZeekDnsLogSink(BaseNode):
    """Generates synthetic Zeek dns.log entries from flow messages."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.output_file: str = configuration.get("output_file", "dns.log")

        output_dir = os.environ.get("ASTRONS_OUTPUT_DIR")
        if output_dir:
            self.output_file = os.path.join(output_dir, os.path.basename(self.output_file))

        # Hostname table: dst_ip → hostname
        self.hostname_table: Dict[str, str] = configuration.get("hostname_table", {})
        # Reverse table: hostname → dst_ip (for port-53 flow query generation)
        self._hostname_list = list(self.hostname_table.items())

        # Default DNS resolver IP
        self.dns_resolver: str = configuration.get("dns_resolver", "8.8.8.8")

        # DGA rate: fraction of queries that are DGA-like NXDOMAIN
        self.dga_rate: float = float(configuration.get("dga_rate", 0.02))

        # DNS cache TTL in sim seconds
        self.cache_ttl: float = float(configuration.get("cache_ttl", 300.0))

        # DNS cache: (src_ip, hostname) → last_query_simtime
        self._dns_cache: Dict[tuple, float] = {}

        # Deterministic RNG
        global_seed = int(configuration.get("seed", 42))
        self.rng = random.Random(f"{global_seed}_{name}")

        self._file: Optional[IO] = None
        self._open_file()
        self._entries_written = 0

        self.env.process(self.run())

    def _open_file(self):
        os.makedirs(os.path.dirname(self.output_file) or ".", exist_ok=True)
        self._file = open(self.output_file, "w")

    def _generate_uid(self) -> str:
        return "C" + "".join(
            self.rng.choice(ZEEK_UID_CHARS) for _ in range(17)
        )

    def _generate_dga_domain(self) -> str:
        """Generate a DGA-like random domain name."""
        length = self.rng.randint(8, 20)
        # Mix of consonants and vowels for pronounceable-ish but suspicious domains
        chars = "".join(self.rng.choice("bcdfghjklmnpqrstvwxyz" if i % 2 == 0
                                         else "aeiou")
                        for i in range(length))
        tld = self.rng.choice(DGA_TLDS)
        return chars + tld

    def _get_hostname(self, dst_ip: str) -> str:
        """Look up hostname for a destination IP, generating one if not in table."""
        hostname = self.hostname_table.get(dst_ip)
        if hostname:
            return hostname
        # Generate a plausible hostname for unknown IPs
        octets = dst_ip.replace(".", "-")
        if dst_ip.startswith(("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                               "172.20.", "172.21.", "172.22.", "172.23.",
                               "172.24.", "172.25.", "172.26.", "172.27.",
                               "172.28.", "172.29.", "172.30.", "172.31.",
                               "192.168.")):
            return f"host-{octets}.internal.corp"
        return f"host-{octets}.external.net"

    def _is_cached(self, src_ip: str, hostname: str, sim_time: float) -> bool:
        """Check if this (src_ip, hostname) was queried within the cache TTL."""
        key = (src_ip, hostname)
        last_ts = self._dns_cache.get(key)
        if last_ts is not None and (sim_time - last_ts) < self.cache_ttl:
            return True
        self._dns_cache[key] = sim_time
        return False

    def _sample_dns_rtt(self) -> float:
        """Sample DNS RTT in seconds from a lognormal distribution.
        Typical DNS RTT is 5-50ms."""
        # log-space mean ~2.7 (≈15ms), std ~0.7
        ms = max(0.5, math.exp(self.rng.gauss(2.7, 0.7)))
        return ms / 1000.0

    def _write_entry(self, entry: dict):
        if self._file:
            self._file.write(json.dumps(entry) + "\n")
            self._entries_written += 1

    def execute(self):
        """Execute generator — receives flow messages, writes dns.log."""
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

                src_ip = data_in.get("src_ip", "0.0.0.0")
                dst_ip = data_in.get("dst_ip", "0.0.0.0")
                dst_port = data_in.get("dst_port", 0)
                flow_start = data_in.get("flow_start", 0.0)
                sim_time = self.env.now

                if dst_port == 53:
                    # Port-53 flow: this IS a DNS query.
                    # Pick a random hostname from the table as the query.
                    if self._hostname_list:
                        ip, hostname = self.rng.choice(self._hostname_list)
                        self._write_dns_entry(
                            ts=flow_start,
                            src_ip=src_ip,
                            src_port=self.rng.randint(1024, 65535),
                            resolver_ip=dst_ip,
                            query=hostname,
                            answer_ip=ip,
                        )
                else:
                    # Non-port-53 flow: generate the DNS lookup that
                    # preceded this connection.
                    hostname = self._get_hostname(dst_ip)
                    if not self._is_cached(src_ip, hostname, sim_time):
                        # DNS lookup happens slightly before the connection
                        dns_ts = flow_start - self.rng.uniform(0.001, 0.05)
                        self._write_dns_entry(
                            ts=dns_ts,
                            src_ip=src_ip,
                            src_port=self.rng.randint(1024, 65535),
                            resolver_ip=self.dns_resolver,
                            query=hostname,
                            answer_ip=dst_ip,
                        )

                # DGA noise: small chance of a suspicious NXDOMAIN query
                if self.rng.random() < self.dga_rate:
                    dga_domain = self._generate_dga_domain()
                    dga_ts = flow_start - self.rng.uniform(0.01, 0.5)
                    self._write_dga_entry(
                        ts=dga_ts,
                        src_ip=src_ip,
                        src_port=self.rng.randint(1024, 65535),
                        resolver_ip=self.dns_resolver,
                        query=dga_domain,
                    )

                processing_time = 0.0
                data_out_list = [data_in.copy()]
            else:
                data_out_list = []
                processing_time = 0.0

    def _write_dns_entry(self, ts: float, src_ip: str, src_port: int,
                          resolver_ip: str, query: str, answer_ip: str):
        """Write a successful DNS resolution entry."""
        uid = self._generate_uid()
        rtt = self._sample_dns_rtt()
        # TTL: 60-3600 seconds, lognormal centered around 300
        ttl = max(60.0, min(86400.0, math.exp(self.rng.gauss(5.7, 0.8))))

        entry = {
            "ts": round(ts, 6),
            "_path": "dns",
            "uid": uid,
            "id.orig_h": src_ip,
            "id.orig_p": src_port,
            "id.resp_h": resolver_ip,
            "id.resp_p": 53,
            "proto": "udp",
            "query": query,
            "qtype_name": "A" if self.rng.random() < 0.95 else "AAAA",
            "qclass_name": "C_INTERNET",
            "rcode_name": "NOERROR",
            "rtt": round(rtt, 6),
            "answers": [answer_ip],
            "TTLs": [round(ttl, 1)],
            "AA": False,
            "TC": False,
            "RD": True,
            "RA": True,
            "rejected": False,
        }
        self._write_entry(entry)

    def _write_dga_entry(self, ts: float, src_ip: str, src_port: int,
                          resolver_ip: str, query: str):
        """Write a DGA-like NXDOMAIN DNS entry."""
        uid = self._generate_uid()
        rtt = self._sample_dns_rtt()

        entry = {
            "ts": round(ts, 6),
            "_path": "dns",
            "uid": uid,
            "id.orig_h": src_ip,
            "id.orig_p": src_port,
            "id.resp_h": resolver_ip,
            "id.resp_p": 53,
            "proto": "udp",
            "query": query,
            "qtype_name": "A",
            "qclass_name": "C_INTERNET",
            "rcode_name": "NXDOMAIN",
            "rtt": round(rtt, 6),
            "AA": False,
            "TC": False,
            "RD": True,
            "RA": True,
            "rejected": True,
        }
        self._write_entry(entry)

    def __del__(self):
        if self._file and not self._file.closed:
            self._file.close()
