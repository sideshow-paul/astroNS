"""
ZeekDhcpLogSink — writes Zeek dhcp.log formatted output.

DHCP is per-device, not per-flow. This sink tracks unique source IPs and
emits a DHCP lease entry on first appearance, then renewal entries every
lease_interval seconds of sim time.

The dhcp-processor consumes these to:
  - Discover devices (IP + MAC association)
  - Capture hostnames (host_name, client_fqdn)
  - Detect OS via DHCP option-55 fingerprint + vendor_class

YAML usage:
    DhcpLogSink:
      type: ZeekDhcpLogSink
      output_file: "dhcp.log"
      site_domain: "tokyo.corp.example.com"
      lease_interval: 14400
"""
import json
import os
import random
import string

from simpy.core import Environment
from nodes.core.base import BaseNode
from typing import Dict, Any, List, Optional, IO, Tuple


# Zeek uid charset (base62-like)
ZEEK_UID_CHARS = string.ascii_letters + string.digits

# OUI prefixes per subnet category (real vendor OUIs)
OUI_BY_CATEGORY = {
    "server":      ["00:14:22", "00:1A:4B", "00:25:B5"],  # Dell, HP, Dell
    "workstation": ["00:1B:21", "3C:22:FB", "A4:83:E7"],  # Intel, Apple, Intel
    "development": ["00:1E:C2", "00:06:1B", "54:E1:AD"],  # Apple, Lenovo, Lenovo
    "iot":         ["00:1E:BD", "00:40:84", "B8:27:EB"],  # Cisco, Honeywell, RPi
    "guest":       ["3C:22:FB", "F0:18:98", "DC:A6:32"],  # Apple, Samsung, RPi
}

# Hostname prefixes per subnet category
HOSTNAME_PREFIX = {
    "server":      "SRV",
    "workstation": "WS",
    "development": "DEV",
    "iot":         "IOT",
    "guest":       "GUEST",
}

# DHCP option-55 fingerprints per OS type
# These are real fingerprint strings that dhcp-processor uses for OS detection
FINGERPRINTS = {
    "windows": "1,15,3,6,44,46,47,31,33,121,249,43",
    "linux":   "1,28,2,3,15,6,119,12,44,47,26,121",
    "macos":   "1,121,3,6,15,119,252,95,44,46",
    "embedded": "1,3,6,12,15,28,42",
}

# vendor_class per OS type
VENDOR_CLASS = {
    "windows": "MSFT 5.0",
    "linux":   "",
    "macos":   "",
    "embedded": "",
}

# OS distribution per subnet category
OS_DISTRIBUTION = {
    "server":      [("linux", 0.70), ("windows", 0.30)],
    "workstation": [("windows", 0.60), ("macos", 0.30), ("linux", 0.10)],
    "development": [("macos", 0.50), ("linux", 0.35), ("windows", 0.15)],
    "iot":         [("embedded", 0.80), ("linux", 0.20)],
    "guest":       [("macos", 0.40), ("windows", 0.35), ("linux", 0.15), ("embedded", 0.10)],
}

# Map subnet names to categories
SUBNET_CATEGORY_KEYWORDS = {
    "server": ["server", "srv", "data_center", "dc", "trading", "network_infra", "lab"],
    "workstation": ["office", "corporate", "call_center"],
    "development": ["engineering", "dev", "development"],
    "iot": ["iot", "sensor", "camera", "building"],
    "guest": ["guest", "visitor", "wifi"],
}


def _classify_subnet(subnet_name: str) -> str:
    """Classify a subnet name into a device category."""
    name_lower = subnet_name.lower()
    for category, keywords in SUBNET_CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return category
    return "workstation"  # default


class ZeekDhcpLogSink(BaseNode):
    """Generates synthetic Zeek dhcp.log entries, one per device per lease interval."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.output_file: str = configuration.get("output_file", "dhcp.log")

        output_dir = os.environ.get("ASTRONS_OUTPUT_DIR")
        if output_dir:
            self.output_file = os.path.join(output_dir, os.path.basename(self.output_file))

        # Site domain for FQDN generation
        self.site_domain: str = configuration.get("site_domain", "corp.example.com")

        # Lease renewal interval in sim seconds (default 4 hours)
        self.lease_interval: float = float(configuration.get("lease_interval", 14400.0))

        # Deterministic RNG
        global_seed = int(configuration.get("seed", 42))
        self.rng = random.Random(f"{global_seed}_{name}")

        # Device registry: src_ip → (last_dhcp_time, mac, hostname, os_type, category)
        self._devices: Dict[str, Tuple[float, str, str, str, str]] = {}

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

    def _generate_mac(self, src_ip: str, category: str) -> str:
        """Generate a deterministic MAC address from IP and category."""
        oui_list = OUI_BY_CATEGORY.get(category, OUI_BY_CATEGORY["workstation"])
        # Use IP to deterministically pick OUI and generate NIC bytes
        ip_rng = random.Random(f"mac_{src_ip}")
        oui = ip_rng.choice(oui_list)
        nic = ":".join(f"{ip_rng.randint(0, 255):02x}" for _ in range(3))
        return f"{oui}:{nic}"

    def _generate_hostname(self, src_ip: str, subnet_name: str, category: str) -> str:
        """Generate a deterministic hostname from IP and subnet."""
        prefix = HOSTNAME_PREFIX.get(category, "HOST")
        octets = src_ip.split(".")
        subnet_short = subnet_name[:3].upper()
        # Use 3rd+4th octets to avoid collisions across subnets
        return f"{prefix}-{subnet_short}-{octets[2]}{octets[3].zfill(3)}"

    def _pick_os(self, category: str, src_ip: str) -> str:
        """Deterministically pick an OS type for a device."""
        dist = OS_DISTRIBUTION.get(category, OS_DISTRIBUTION["workstation"])
        ip_rng = random.Random(f"os_{src_ip}")
        r = ip_rng.random()
        cumulative = 0.0
        for os_type, weight in dist:
            cumulative += weight
            if r < cumulative:
                return os_type
        return dist[-1][0]

    def _write_entry(self, entry: dict):
        if self._file:
            self._file.write(json.dumps(entry) + "\n")
            self._entries_written += 1

    def _emit_dhcp(self, ts: float, src_ip: str, mac: str, hostname: str,
                   os_type: str):
        """Write a DHCP lease entry."""
        uid = self._generate_uid()
        fqdn = f"{hostname}.{self.site_domain}"

        entry = {
            "ts": round(ts, 6),
            "_path": "dhcp",
            "uid": uid,
            "id.orig_h": src_ip,
            "id.orig_p": 68,
            "id.resp_h": "255.255.255.255",
            "id.resp_p": 67,
            "mac": mac,
            "assigned_ip": src_ip,
            "requested_addr": src_ip,
            "client_addr": "0.0.0.0",
            "host_name": hostname,
            "client_fqdn": fqdn,
            "domain": self.site_domain,
            "fingerprint": FINGERPRINTS.get(os_type, FINGERPRINTS["linux"]),
            "vendor_class": VENDOR_CLASS.get(os_type, ""),
            "lease_time": int(self.lease_interval),
            "msg_types": ["DISCOVER", "OFFER", "REQUEST", "ACK"],
        }

        self._write_entry(entry)

    def execute(self):
        """Execute generator — tracks devices and emits DHCP entries."""
        processing_time: float = 0.0
        data_out_list: List[Dict] = []

        while True:
            data_in = yield (0, processing_time, data_out_list)

            if data_in:
                if data_in.get("_skip"):
                    data_out_list = [data_in.copy()]
                    processing_time = 0.0
                    continue

                src_ip = data_in.get("src_ip", "0.0.0.0")
                flow_start = data_in.get("flow_start", 0.0)
                subnet_name = data_in.get("agg_subnet", data_in.get("subnet_name", "Unknown"))

                device = self._devices.get(src_ip)

                if device is None:
                    # First time seeing this device — emit initial DHCP lease
                    category = _classify_subnet(subnet_name)
                    mac = self._generate_mac(src_ip, category)
                    hostname = self._generate_hostname(src_ip, subnet_name, category)
                    os_type = self._pick_os(category, src_ip)

                    self._emit_dhcp(flow_start, src_ip, mac, hostname, os_type)
                    self._devices[src_ip] = (flow_start, mac, hostname, os_type, category)
                else:
                    last_ts, mac, hostname, os_type, category = device
                    # Check if lease renewal is due
                    if (flow_start - last_ts) >= self.lease_interval:
                        self._emit_dhcp(flow_start, src_ip, mac, hostname, os_type)
                        self._devices[src_ip] = (flow_start, mac, hostname, os_type, category)

                processing_time = 0.0
                data_out_list = [data_in.copy()]
            else:
                data_out_list = []
                processing_time = 0.0

    def __del__(self):
        if self._file and not self._file.closed:
            self._file.close()
