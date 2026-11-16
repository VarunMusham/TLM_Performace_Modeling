"""Offline metrics. Admission cohorts and completion windows remain distinct."""
import math
import statistics
from .events import TERMINAL
from .config import require


def distribution(values):
    values = sorted(values)
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None, "p95": None, "p99": None}
    return {"count": len(values), "min": values[0], "max": values[-1], "mean": statistics.mean(values),
            "median": statistics.median(values), "p95": values[math.ceil(.95*len(values))-1],
            "p99": values[math.ceil(.99*len(values))-1]}


def union_duration(intervals, start, end):
    intervals = sorted((max(a, start), min(b, end)) for a, b in intervals if a < end and b > start)
    total, cursor = 0, start
    for a, b in intervals:
        total += max(0, b-max(a, cursor))
        cursor = max(cursor, b)
    return total


def occupancy(changes, start, end, capacity):
    level, cursor, area, peak = 0, start, 0, 0
    previous = -1
    for tick, new_level in changes:
        require(tick >= previous and 0 <= new_level <= capacity, "Invalid occupancy changes")
        previous = tick
        if tick <= start:
            level = new_level
            peak = level
        elif tick < end:
            area += level*(tick-cursor)
            cursor, level = tick, new_level
            peak = max(peak, level)
        else:
            break
    area += level*(end-cursor)
    return {"average": area/(end-start), "peak": peak, "capacity": capacity}


def analyze(events, start, end):
    require(start < end, "Invalid metric window")
    groups, expiries, changes = {}, [], []
    control, last_reload, last_expiry = 0, None, None
    timeout_cycles, output_latency = [], []
    for e in events:
        tick = int(e["observed_tick"])
        if e["event"] == "reset":
            control, last_reload, last_expiry = 0, None, None
        elif e["event"] == "commit_write":
            addr = int(e.get("attributes", {}).get("address", -1))
            value = int(e["value"])
            if addr == 0:
                if not control & 1 and value & 1:
                    last_reload = e
                control = value
            elif addr == 12 and control & 1:
                last_reload = e
        elif e["event"] == "expiry":
            if start <= tick < end and last_reload is not None and "cycle" in e and "cycle" in last_reload:
                require(e["clock_id"] == last_reload["clock_id"] and e["epoch"] == last_reload["epoch"], "Clock-domain mismatch")
                timeout_cycles.append(int(e["cycle"])-int(last_reload["cycle"]))
            last_expiry = tick
        elif e["event"] in {"irq", "reset_request"} and e["value"] == "1" and last_expiry is not None and start <= tick < end:
            output_latency.append(tick-last_expiry)
        if "transaction_id" in e:
            groups.setdefault(e["transaction_id"], []).append(e)
        if e["event"] == "expiry" and start <= tick < end:
            expiries.append(e["observed_tick"])
        if e["event"] == "submit":
            changes.append((int(e["observed_tick"]), 1))
        elif e["event"] in TERMINAL:
            changes.append((int(e["observed_tick"]), 0))
    latencies, queue_delays, edge_delays, busy = [], [], [], []
    admitted = completed = failed = outstanding = bytes_completed = completions = offered = 0
    for txid, rows in groups.items():
        submits = [e for e in rows if e["event"] == "submit"]
        require(len(submits) == 1, f"Duplicate/missing admission: {txid}")
        entry = int(submits[0]["observed_tick"])
        ready = [int(e["observed_tick"]) for e in rows if e["event"] == "peq_ready"]
        terminal = [e for e in rows if e["event"] in TERMINAL]
        require(len(terminal) <= 1 and len(ready) <= 1, "Duplicate lifecycle event")
        finish = int(terminal[0]["observed_tick"]) if terminal else None
        require(finish is None or finish >= entry, "Negative latency")
        cohort = start <= entry < end
        if cohort:
            admitted += 1
            offered += 1  # WDT accepts every offered call; one outstanding.
            if finish is None:
                outstanding += 1
            elif terminal[0]["event"] in {"access_error", "reset_cancel"}:
                failed += 1
            else:
                completed += 1
                latencies.append(finish-entry)
                if ready:
                    queue_delays.append(ready[0]-entry)
                    edge_delays.append(finish-ready[0])
        if finish is not None and start <= finish < end and terminal[0]["event"] in {"commit_read", "commit_write"}:
            bytes_completed += terminal[0].get("payload_bytes", 0)
            completions += 1
        busy.append((entry, finish if finish is not None else end))
    require(admitted == completed+failed+outstanding, "Conservation failure")
    return {"schema_version": "1", "window": {"start_tick": str(start), "end_tick": str(end), "convention": "[start,end)"},
            "units": {"tick": "ns", "throughput": "bytes/ns"},
            "population": "admission cohort followed through drain; throughput uses completion window",
            "quantiles": "nearest rank ceil(p*N)", "small_sample": len(latencies) < 100,
            "accounting": {"admitted": admitted, "completed": completed, "failed_cancelled": failed,
                           "outstanding_censored": outstanding, "conserved": True},
            "latency_tick": distribution(latencies), "peq_delay_tick": distribution(queue_delays),
            "edge_wait_tick": distribution(edge_delays),
            "wdt_timeout_cycles": distribution(timeout_cycles),
            "output_assertion_after_expiry_tick": distribution(output_latency),
            "output_visibility": "decision edge; signal visible in following kernel update, not a measured hardware delay",
            "completion_window": {"transactions": completions, "payload_bytes": bytes_completed,
                                  "payload_bytes_per_ns": bytes_completed/(end-start)},
            "offered_per_ns": offered/(end-start), "accepted_per_ns": admitted/(end-start),
            "inflight": occupancy(changes, start, end, 1),
            "register_busy_fraction": union_duration(busy, start, end)/(end-start),
            "expiry_ticks": expiries, "wire_throughput": None, "internal_queue_wait": None,
            "stalls": None, "unavailable_reason": "WDT exposes no wire, queue-service, or stall mechanism"}
