"""IP-independent transaction evidence, accounting and timing comparison."""
import csv
from pathlib import Path
from .config import fields, integer, require, MAX_TICK
from .metrics import distribution, occupancy
from .storage import parse_json

KINDS = {"offer", "accept", "complete", "fail", "cancel", "reject"}
TERMINAL = {"complete", "fail", "cancel"}
COLUMNS = ("sequence", "tick", "event", "transaction_id", "payload_bytes")


def import_csv(path, adapter, run_id):
    mapping = adapter.get("trace", {}).get("columns", {key: key for key in COLUMNS})
    event_map = adapter.get("trace", {}).get("event_map", {})
    events = []
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames), "Trace has missing/duplicate CSV headers")
        require(set(mapping.values()) <= set(reader.fieldnames), f"Trace needs CSV columns: {', '.join(mapping.values())}")
        for row in reader:
            require(None not in row and all(value is not None for value in row.values()), f"Malformed CSV row {reader.line_num}")
            values = {key: row[column] for key, column in mapping.items()}
            raw_kind = values["event"]
            events.append({"schema_version": "transaction-1", "run_id": run_id,
                           "sequence": str(integer(values["sequence"], "trace sequence", 1)),
                           "observed_tick": str(integer(values["tick"], "trace tick")),
                           "time_resolution_fs": str(integer(adapter["time_resolution_fs"], "time resolution", 1)),
                           "event": event_map.get(raw_kind, raw_kind), "transaction_id": values["transaction_id"],
                           "payload_bytes": integer(values["payload_bytes"], "payload bytes") if values["payload_bytes"] else None})
    validate_events(events)
    return events


def validate_events(events):
    require(bool(events), "No transaction events were captured")
    previous, resolution, run_id = -1, None, None
    required = {"schema_version", "run_id", "sequence", "observed_tick", "time_resolution_fs",
                "event", "transaction_id", "payload_bytes"}
    for index, event in enumerate(events, 1):
        fields(event, required, required)
        require(event["schema_version"] == "transaction-1", "Unsupported transaction event version")
        require(isinstance(event["event"], str) and event["event"] in KINDS, "Unsupported transaction event")
        require(isinstance(event["transaction_id"], str) and 0 < len(event["transaction_id"]) <= 256, "Missing/oversized transaction ID")
        require(isinstance(event["run_id"], str) and event["run_id"], "Missing run ID")
        for key in ("sequence", "observed_tick", "time_resolution_fs"):
            value = event[key]
            require(isinstance(value, str) and str(integer(value, key)) == value, f"{key} must be a normalized integer string")
        require(int(event["sequence"]) == index, "Transaction trace sequence loss/duplicate")
        tick = int(event["observed_tick"])
        require(tick >= previous, "Transaction trace time moved backwards")
        require(int(event["time_resolution_fs"]) > 0, "Time resolution must be positive")
        resolution = resolution or event["time_resolution_fs"]
        run_id = run_id or event["run_id"]
        require(event["time_resolution_fs"] == resolution and event["run_id"] == run_id, "Mixed run IDs or time resolutions")
        if event["payload_bytes"] is not None:
            require(type(event["payload_bytes"]) is int, "Payload size must be an integer or null")
            integer(event["payload_bytes"], "payload_bytes")
        previous = tick
    return events


def read_events(path):
    with Path(path).open(encoding="utf-8") as stream:
        return validate_events([parse_json(line) for line in stream])


def analyze(events, start, end, stop):
    validate_events(events)
    require(0 <= start < end <= stop <= MAX_TICK, "Require start < end <= capture stop")
    groups, changes, level, peak = {}, [], 0, 0
    for event in events:
        tick, kind, txid = int(event["observed_tick"]), event["event"], event["transaction_id"]
        require(tick <= stop, "Event occurs after capture stop")
        group = groups.setdefault(txid, {})
        require(kind not in group, f"Duplicate {kind}: {txid}")
        require(not (TERMINAL | {"reject"}) & group.keys(), f"Event after terminal outcome: {txid}")
        if kind == "offer":
            require(not group, f"Offer after admission: {txid}")
        elif kind == "accept":
            level += 1
            peak = max(peak, level)
            changes.append((tick, level))
        elif kind == "reject":
            require("offer" in group and "accept" not in group, f"Rejection requires an unaccepted offer: {txid}")
        else:
            require("accept" in group, f"Terminal event without admission: {txid}")
            level -= 1
            changes.append((tick, level))
        group[kind] = event

    admitted = completed = failed = outstanding = completions = known_bytes = unknown_sizes = 0
    offers = rejected = not_admitted = 0
    latency, admission_wait = [], []
    total = {"offered": 0, "admitted": 0, "completed": 0, "failed_cancelled": 0, "rejected": 0, "outstanding": 0}
    offer_visibility = True
    for group in groups.values():
        offer, accept = group.get("offer"), group.get("accept")
        terminal = next((group[k] for k in ("complete", "fail", "cancel") if k in group), None)
        total["offered"] += offer is not None
        total["admitted"] += accept is not None
        total["rejected"] += "reject" in group
        total["completed"] += "complete" in group
        total["failed_cancelled"] += "fail" in group or "cancel" in group
        total["outstanding"] += accept is not None and terminal is None
        if accept and not offer:
            offer_visibility = False
        if offer and start <= int(offer["observed_tick"]) < end:
            offers += 1
            rejected += "reject" in group
            not_admitted += accept is None and "reject" not in group
        if accept and start <= int(accept["observed_tick"]) < end:
            admitted += 1
            if offer:
                admission_wait.append(int(accept["observed_tick"])-int(offer["observed_tick"]))
            if terminal is None:
                outstanding += 1
            elif terminal["event"] == "complete":
                completed += 1
                latency.append(int(terminal["observed_tick"])-int(accept["observed_tick"]))
            else:
                failed += 1
        if "complete" in group and start <= int(group["complete"]["observed_tick"]) < end:
            completions += 1
            size = group["complete"]["payload_bytes"]
            if size is None:
                unknown_sizes += 1
            else:
                known_bytes += size
    require(admitted == completed+failed+outstanding, "Admission conservation failure")
    resolution = int(events[0]["time_resolution_fs"])
    duration = (end-start)*resolution/10**15
    histogram = []
    if latency:
        width = max(1, (max(latency)-min(latency)+10)//10)
        for low in range(min(latency), max(latency)+1, width):
            histogram.append({"start_tick": str(low), "end_tick": str(low+width),
                              "count": sum(low <= value < low+width for value in latency)})
    return {"schema_version": "transaction-metrics-1", "time_resolution_fs": str(resolution),
            "window": {"start_tick": str(start), "end_tick": str(end), "stop_tick": str(stop), "convention": "[start,end)"},
            "population": "Admission cohort followed through capture stop; throughput uses successful completions in the window",
            "accounting": {"admitted": admitted, "completed": completed, "failed_cancelled": failed,
                           "outstanding_censored": outstanding, "conserved": True},
            "all_transactions": total,
            "offered": offers if offer_visibility else None, "rejected_offer_cohort": rejected,
            "unaccepted_offer_cohort": not_admitted, "offer_visibility_complete": offer_visibility,
            "latency_tick": distribution(latency), "admission_wait_tick": distribution(admission_wait),
            "latency_histogram": histogram, "small_sample": len(latency) < 100,
            "completion_window": {"transactions": completions, "known_payload_bytes": known_bytes,
                                  "unknown_payload_sizes": unknown_sizes,
                                  "payload_bytes_per_second": None if unknown_sizes else known_bytes/duration,
                                  "transactions_per_second": completions/duration},
            "inflight": occupancy(changes, start, end, peak),
            "unavailable": ["Internal queue, credit, stall and wire-bandwidth metrics require additional IP-specific probes"],
            "qualification": "Boundary measurements only; model accuracy requires independent reference evidence"}


def compare(left, right, tolerance=0):
    validate_events(left)
    validate_events(right)
    tolerance = integer(tolerance, "tolerance")
    require(left[0]["time_resolution_fs"] == right[0]["time_resolution_fs"], "Comparison requires identical time resolutions")
    for events in (left, right):
        stop = max(1, int(events[-1]["observed_tick"]))
        analyze(events, 0, stop, stop)  # Reject illegal lifecycles before comparing them.
    def index(events):
        result = {}
        for event in events:
            key = (event["transaction_id"], event["event"])
            require(key not in result, f"Duplicate comparison identity: {key}")
            result[key] = event
        return result
    a, b = index(left), index(right)
    differences, maximum = [], 0
    for key in sorted(a.keys() | b.keys()):
        x, y = a.get(key), b.get(key)
        reason = None
        if x is None or y is None:
            reason = "missing_event"
        else:
            delta = abs(int(x["observed_tick"])-int(y["observed_tick"]))
            maximum = max(maximum, delta)
            if delta > tolerance:
                reason = "timing"
            elif x["payload_bytes"] != y["payload_bytes"]:
                reason = "payload_bytes"
        if reason:
            differences.append({"key": key, "reason": reason, "left": x, "right": y})
    differences.sort(key=lambda item: (int((item["left"] or item["right"])["observed_tick"]), item["key"]))
    return {"status": "fail" if differences else "pass", "mode": "boundary_timing",
            "tolerance_tick": str(tolerance), "maximum_discrepancy_tick": str(maximum),
            "mismatch_count": len(differences), "first_mismatch": differences[0] if differences else None,
            "differences": differences[:100],
            "scope": "Transaction boundary timing/size agreement; no payload-content or protocol-equivalence claim"}
