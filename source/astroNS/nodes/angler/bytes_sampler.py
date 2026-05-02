"""
BytesSampler — lognormal bytes/packets assignment per (src, dst) pair.

Receives flow messages with src_ip and dst_ip, and adds orig_bytes,
resp_bytes, orig_pkts, and resp_pkts fields sampled from lognormal
distributions fitted to observed traffic per (source, destination) pair.

YAML usage:
    Bytes_10_0_1_50:
      type: BytesSampler
      device_ip: "10.0.1.50"
      bytes_profiles:
        "8.8.8.8":
          bytes_log_mean: 7.2
          bytes_log_variance: 1.5
          packets_log_mean: 3.1
          packets_log_variance: 0.8
          response_ratio: 5.2
      SubnetAgg_IoT: ~
"""
import math
import random

from simpy.core import Environment
from nodes.core.base import BaseNode
from typing import Dict, Any, List, Optional, Callable


class BytesSampler(BaseNode):
    """Samples bytes and packets from lognormal distributions for each
    (source, destination) pair, applying the observed response ratio."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())

        self.device_ip: str = configuration.get("device_ip", "0.0.0.0")
        self.bytes_profiles: Dict[str, Dict[str, Any]] = configuration.get(
            "bytes_profiles", {}
        )

        # Default profile for unknown destinations
        self.default_profile = {
            "bytes_log_mean": 6.0,    # ~400 bytes
            "bytes_log_variance": 2.0,
            "packets_log_mean": 1.5,  # ~4 packets
            "packets_log_variance": 1.0,
            "response_ratio": 2.0,
        }

        # Deterministic RNG
        global_seed = int(configuration.get("seed", 42))
        self.rng = random.Random(f"{global_seed}_{name}")

        self.env.process(self.run())

    def _sample_lognormal(self, log_mean: float, log_var: float) -> float:
        """Sample from lognormal given log-space mean and variance."""
        if log_mean is None:
            log_mean = 0.0
        if log_var is None or log_var <= 0:
            return max(1.0, math.exp(log_mean))

        log_std = math.sqrt(log_var)
        return max(1.0, math.exp(self.rng.gauss(log_mean, log_std)))

    def execute(self):
        """Execute generator — receives flow messages, adds bytes/packets."""
        processing_time: float = 0.0
        data_out_list: List[Dict] = []

        while True:
            data_in = yield (0, processing_time, data_out_list)

            if data_in:
                data_out = data_in.copy()

                # Skip placeholder flows
                if data_in.get("_skip"):
                    data_out_list = [data_out]
                    processing_time = 0.0
                    continue

                dst_ip = data_in.get("dst_ip", "0.0.0.0")
                profile = self.bytes_profiles.get(dst_ip, self.default_profile)

                # Sample orig_bytes
                orig_bytes = int(
                    self._sample_lognormal(
                        profile.get("bytes_log_mean"),
                        profile.get("bytes_log_variance"),
                    )
                )

                # Sample orig_pkts
                orig_pkts = max(
                    1,
                    int(
                        self._sample_lognormal(
                            profile.get("packets_log_mean"),
                            profile.get("packets_log_variance"),
                        )
                    ),
                )

                # Apply response ratio
                resp_ratio = profile.get("response_ratio") or 1.0
                resp_bytes = int(orig_bytes * resp_ratio)
                resp_pkts = max(1, int(orig_pkts * resp_ratio * 0.8))

                data_out["orig_bytes"] = orig_bytes
                data_out["resp_bytes"] = resp_bytes
                data_out["orig_pkts"] = orig_pkts
                data_out["resp_pkts"] = resp_pkts
                data_out[self.msg_size_key] = orig_bytes + resp_bytes

                processing_time = 0.0
                data_out_list = [data_out]

                print(
                    self.log_prefix(data_in["ID"])
                    + f"Bytes: orig={orig_bytes} resp={resp_bytes} "
                    + f"pkts={orig_pkts}/{resp_pkts}"
                )
            else:
                data_out_list = []
                processing_time = 0.0
