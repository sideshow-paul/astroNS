#!/usr/bin/env python3
"""
Integration test: verify StreamingStats accumulators match legacy list-based
statistics after running a real astroNS simulation.

Cross-validates get_stats() against numpy calculations on the raw lists
that BaseNode still populates when lean_mode is off.
"""

import sys
import os
import math

# Run from the astroNS source dir
os.chdir(os.path.join(os.path.dirname(__file__), "astroNS"))
sys.path.insert(0, ".")

# Suppress sim startup noise
from io import StringIO
old_stdout = sys.stdout
sys.stdout = StringIO()

import importlib.util
spec = importlib.util.spec_from_file_location("sim", "astroNS.py")
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)

from nodes.core.base import BaseNode

# Reset class state and run sim
BaseNode.nodes = {}
BaseNode.node_list = []
BaseNode.mapping = {}
BaseNode.msg_history = {}
BaseNode.lean_mode = False  # ensure legacy lists are populated

sim.main("../models/angler_ttl_test.yml", node_stats=True)
sys.stdout = old_stdout

import numpy as np

# ─── Cross-validation: streaming stats vs legacy lists ───────────────

print("=" * 100)
print("STREAMING STATS INTEGRATION TEST")
print("=" * 100)

TOLERANCE_MEAN = 1e-10   # Welford should be exact to float precision
TOLERANCE_STD = 1e-6     # tiny float rounding
TOLERANCE_P = 0.15       # P2 quantile: 15% relative tolerance (approximate algorithm)

errors = []
nodes_tested = 0
metrics_checked = 0

for name in sorted(BaseNode.nodes.keys()):
    node = BaseNode.nodes[name]
    stats = node.get_stats()
    n = stats["msgs_processed"]
    if n == 0:
        continue

    nodes_tested += 1

    # Cross-validate each metric
    for metric_name, streaming, legacy_list in [
        ("wait_time", stats["wait_time"], node.wait_times),
        ("processing_time", stats["processing_time"], node.processing_times),
        ("delay", stats["delay"], node.delay_till_next_msg),
        ("data_size", stats["data_size"], node.data_sizes),
    ]:
        arr = np.array(legacy_list)
        if len(arr) == 0:
            continue

        metrics_checked += 1

        # Count
        if streaming["count"] != len(arr):
            errors.append(f"{name}/{metric_name}: count {streaming['count']} != {len(arr)}")

        # Mean
        expected_mean = float(np.mean(arr))
        if abs(streaming["mean"] - expected_mean) > TOLERANCE_MEAN:
            errors.append(
                f"{name}/{metric_name}: mean {streaming['mean']:.10f} != {expected_mean:.10f}"
            )

        # Std (population)
        expected_std = float(np.std(arr))
        if abs(streaming["std"] - expected_std) > TOLERANCE_STD:
            errors.append(
                f"{name}/{metric_name}: std {streaming['std']:.10f} != {expected_std:.10f}"
            )

        # Min
        expected_min = float(np.min(arr))
        if streaming["min"] != expected_min:
            errors.append(
                f"{name}/{metric_name}: min {streaming['min']} != {expected_min}"
            )

        # Max
        expected_max = float(np.max(arr))
        if streaming["max"] != expected_max:
            errors.append(
                f"{name}/{metric_name}: max {streaming['max']} != {expected_max}"
            )

        # Sum
        expected_sum = float(np.sum(arr))
        if abs(streaming["sum"] - expected_sum) > TOLERANCE_MEAN:
            errors.append(
                f"{name}/{metric_name}: sum {streaming['sum']:.10f} != {expected_sum:.10f}"
            )

        # Quantiles (P2 is approximate — check within relative tolerance)
        for pname, pkey in [("p25", 0.25), ("p75", 0.75), ("p90", 0.90)]:
            expected_p = float(np.percentile(arr, pkey * 100))
            actual_p = streaming[pname]
            # For all-zero arrays, both should be 0
            if expected_p == 0.0 and actual_p == 0.0:
                continue
            if expected_p == 0.0:
                # Can't compute relative error; use absolute
                if abs(actual_p) > 0.01:
                    errors.append(
                        f"{name}/{metric_name}/{pname}: {actual_p:.6f} != {expected_p:.6f} (expected 0)"
                    )
                continue
            rel_err = abs(actual_p - expected_p) / abs(expected_p)
            if rel_err > TOLERANCE_P:
                errors.append(
                    f"{name}/{metric_name}/{pname}: {actual_p:.6f} vs expected {expected_p:.6f} "
                    f"(rel_err={rel_err:.2%} > {TOLERANCE_P:.0%})"
                )

# ─── Print detailed results for nodes with non-zero processing ───────

print()
print("─── Nodes with non-zero processing times ───")
print()
header = f"{'Node':<35s} {'Msgs':>5s} │ {'Proc Mean':>10s} {'Proc Std':>10s} {'Proc P25':>10s} {'Proc P75':>10s} {'Proc P90':>10s} {'Proc Min':>10s} {'Proc Max':>10s}"
print(header)
print("─" * len(header))

for name in sorted(BaseNode.nodes.keys()):
    node = BaseNode.nodes[name]
    s = node.get_stats()
    p = s["processing_time"]
    if p["count"] == 0 or p["max"] == 0:
        continue
    print(
        f"{name:<35s} {p['count']:5d} │ "
        f"{p['mean']:10.6f} {p['std']:10.6f} {p['p25']:10.6f} {p['p75']:10.6f} {p['p90']:10.6f} "
        f"{p['min']:10.6f} {p['max']:10.6f}"
    )

print()
print("─── Nodes with non-zero data sizes ───")
print()
header = f"{'Node':<35s} {'Msgs':>5s} │ {'Size Mean':>10s} {'Size Std':>10s} {'Size P25':>10s} {'Size P75':>10s} {'Size P90':>10s} {'Size Min':>10s} {'Size Max':>10s}"
print(header)
print("─" * len(header))

for name in sorted(BaseNode.nodes.keys()):
    node = BaseNode.nodes[name]
    s = node.get_stats()
    d = s["data_size"]
    if d["count"] == 0 or d["max"] == 0:
        continue
    print(
        f"{name:<35s} {d['count']:5d} │ "
        f"{d['mean']:10.1f} {d['std']:10.1f} {d['p25']:10.1f} {d['p75']:10.1f} {d['p90']:10.1f} "
        f"{d['min']:10.1f} {d['max']:10.1f}"
    )

# ─── Cross-validation comparison table ───────────────────────────────

print()
print("─── Cross-validation: streaming vs numpy (non-zero metrics only) ───")
print()
header = f"{'Node/Metric':<45s} │ {'Streaming':>12s} {'NumPy':>12s} {'Diff':>12s} {'Status':>8s}"
print(header)
print("─" * len(header))

for name in sorted(BaseNode.nodes.keys()):
    node = BaseNode.nodes[name]
    stats = node.get_stats()
    if stats["msgs_processed"] == 0:
        continue

    for metric_name, streaming, legacy_list in [
        ("processing_time", stats["processing_time"], node.processing_times),
        ("data_size", stats["data_size"], node.data_sizes),
    ]:
        arr = np.array(legacy_list)
        if len(arr) == 0 or np.max(arr) == 0:
            continue

        np_mean = float(np.mean(arr))
        np_std = float(np.std(arr))
        np_p90 = float(np.percentile(arr, 90))

        # Mean comparison
        diff = abs(streaming["mean"] - np_mean)
        status = "OK" if diff < 1e-10 else "FAIL"
        label = f"{name}/{metric_name}/mean"
        print(f"{label:<45s} │ {streaming['mean']:12.6f} {np_mean:12.6f} {diff:12.2e} {status:>8s}")

        # Std comparison
        diff = abs(streaming["std"] - np_std)
        status = "OK" if diff < 1e-6 else "FAIL"
        label = f"{name}/{metric_name}/std"
        print(f"{label:<45s} │ {streaming['std']:12.6f} {np_std:12.6f} {diff:12.2e} {status:>8s}")

        # P90 comparison
        diff = abs(streaming["p90"] - np_p90)
        rel = diff / np_p90 if np_p90 != 0 else 0
        status = "OK" if rel < 0.15 else "FAIL"
        label = f"{name}/{metric_name}/p90"
        print(f"{label:<45s} │ {streaming['p90']:12.6f} {np_p90:12.6f} {diff:12.2e} {status:>8s}")

# ─── Summary ─────────────────────────────────────────────────────────

print()
print("=" * 100)
print(f"Nodes tested: {nodes_tested}")
print(f"Metrics cross-validated: {metrics_checked}")
if errors:
    print(f"FAILURES: {len(errors)}")
    for e in errors:
        print(f"  FAIL: {e}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
    sys.exit(0)
