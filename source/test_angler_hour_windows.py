"""
Tests for time-windowed what-if scenarios: hour_windows.active_window,
NetworkSegment.degrade_windows, and SiteGateway.constraint_windows.

Drives fresh execute() generators directly (send a flow, inspect the
yielded (delay, processing_time, data_out_list) tuple) so window
behavior is checked deterministically at specific sim clock values.
"""
import sys
import os
import datetime
import simpy

# Add source directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'astroNS'))

from nodes.angler.hour_windows import active_window
from nodes.angler.network_segment import NetworkSegment
from nodes.angler.site_gateway import SiteGateway


def make_flow(**overrides):
    flow = {
        "ID": "test-flow",
        "src_ip": "10.0.1.10",
        "dst_ip": "52.94.237.74",
        "orig_bytes": 10_000,
        "resp_bytes": 40_000,
        "qos_class": "AF",
    }
    flow.update(overrides)
    return flow


def make_env():
    """SimPy environment with the astroNS decorations log_prefix needs."""
    env = simpy.Environment()
    env.end_simtime = 14400
    env.now_datetime = lambda: datetime.datetime(2026, 1, 6) + datetime.timedelta(
        seconds=env.now
    )
    return env


def drive(node, env, now, flow):
    """Send one flow through a fresh execute() generator at sim time `now`."""
    env._now = now
    gen = node.execute()
    gen.send(None)  # prime: runs to the first yield
    return gen.send(flow)  # (delay, processing_time, data_out_list)


def test_active_window():
    windows = [{"start_hour": 12, "end_hour": 16, "latency_multiplier": 3.0}]
    # start_hour 8, env.now in seconds since sim start
    assert active_window(0, 8, windows) is None                # hour 8
    assert active_window(4 * 3600, 8, windows) is windows[0]   # hour 12
    assert active_window(7 * 3600 + 1800, 8, windows) is windows[0]  # hour 15:30
    assert active_window(8 * 3600, 8, windows) is None         # hour 16 (exclusive)
    assert active_window(0, 12, windows) is windows[0]         # starts inside

    # Midnight wrap: 22 -> 2
    wrap = [{"start_hour": 22, "end_hour": 2}]
    assert active_window(0, 23, wrap) is wrap[0]
    assert active_window(2 * 3600, 23, wrap) is wrap[0]        # hour 1
    assert active_window(3 * 3600, 23, wrap) is None           # hour 2

    assert active_window(0, 0, []) is None


def _make_segment(env, **extra):
    config = {
        "segment_type": "wan",
        "subnet": "WAN",
        "hop_depth": 4,
        "hop_latency_ms": 14.0,
        "jitter_ms": 0.0,
        "loss_rate": 0.0,
        "start_hour": 8,
        "seed": 42,
    }
    config.update(extra)
    return NetworkSegment(env, "WAN_test", config)


def test_network_segment_degrade_window_latency():
    env = make_env()
    seg = _make_segment(env, degrade_windows=[
        {"start_hour": 9, "end_hour": 10, "latency_multiplier": 10.0},
    ])

    # Hour 8 — baseline 14ms
    _, proc, out = drive(seg, env, 0, make_flow())
    assert abs(proc - 0.014) < 1e-9
    assert out[0]["seg_latency_ms"] == 14.0

    # Hour 9 — degraded 140ms
    _, proc, out = drive(seg, env, 3600, make_flow())
    assert abs(proc - 0.140) < 1e-9
    assert out[0]["seg_latency_ms"] == 140.0

    # Hour 10 — recovered
    _, proc, _ = drive(seg, env, 2 * 3600, make_flow())
    assert abs(proc - 0.014) < 1e-9


def test_network_segment_degrade_window_loss():
    env = make_env()
    seg = _make_segment(env, degrade_windows=[
        {"start_hour": 9, "end_hour": 10, "latency_multiplier": 1.0, "loss_rate": 1.0},
    ])

    # Hour 8 — no loss
    _, _, out = drive(seg, env, 0, make_flow())
    assert len(out) == 1

    # Hour 9 — loss_rate 1.0 drops everything
    _, _, out = drive(seg, env, 3600, make_flow())
    assert out == []
    assert seg.total_dropped == 1

    # Hour 10 — no loss again
    _, _, out = drive(seg, env, 2 * 3600, make_flow())
    assert len(out) == 1


def test_network_segment_without_windows_unchanged():
    env = make_env()
    seg = _make_segment(env)
    _, proc, out = drive(seg, env, 3600, make_flow())
    assert abs(proc - 0.014) < 1e-9
    assert len(out) == 1


def test_site_gateway_constraint_window():
    env = make_env()
    gw = SiteGateway(env, "SiteGateway_test", {
        "site_id": "test-site",
        "uplink_capacity_bps": 1_000_000_000,
        "start_hour": 8,
        "constraint_windows": [
            {"start_hour": 10, "end_hour": 11, "capacity_bps": 2_000_000},
        ],
        "provider_prefixes": {"AWS": ["52."]},
    })

    big_flow = make_flow(orig_bytes=500_000, resp_bytes=500_000)  # 8 Mbit

    # Hour 8 — 1 Gbps uplink, 8 Mbit is nowhere near congestion
    _, proc, out = drive(gw, env, 0, big_flow)
    assert proc == 0.0
    assert out[0]["dc_provider"] == "AWS"

    # Hour 10 — 2 Mbps uplink, same flow saturates it (rho >= 1 -> AF max delay)
    _, proc, out = drive(gw, env, 2 * 3600, big_flow)
    assert abs(proc - 0.100) < 1e-9  # AF max_delay_ms = 100
    assert out[0]["uplink_delay_ms"] == 100.0

    # Hour 11 — window over, back to 1 Gbps
    _, proc, _ = drive(gw, env, 3 * 3600, big_flow)
    assert proc == 0.0


if __name__ == "__main__":
    test_active_window()
    test_network_segment_degrade_window_latency()
    test_network_segment_degrade_window_loss()
    test_network_segment_without_windows_unchanged()
    test_site_gateway_constraint_window()
    print("All hour-window tests passed.")
