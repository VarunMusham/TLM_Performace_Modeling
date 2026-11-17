"""Canonical normalization and strict lifecycle checks for the WDT adapter."""
import csv
import json
from pathlib import Path
from .config import require, address, fields, integer, MAX_TICK
from .storage import exclusive_text, parse_json

TERMINAL = {"commit_read", "commit_write", "access_error", "reset_cancel"}
KINDS = TERMINAL | {"submit", "peq_ready", "reset", "expiry", "irq", "reset_request"}
COLUMNS = ["tick", "delta", "sequence", "event", "transaction_id", "address", "value"]


def read_pilot(path):
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        require(reader.fieldnames == COLUMNS, "Pilot trace columns differ")
        rows = []
        for r in reader:
            require(None not in r and all(v is not None for v in r.values()), "Malformed CSV row")
            require(r["event"] in KINDS, f"Unknown event: {r['event']}")
            row = {k: (v if k == "event" else int(v)) for k, v in r.items()}
            require(all(v >= 0 for k, v in row.items() if k != "event"), "Negative trace field")
            rows.append(row)
    require(bool(rows), "Empty trace")
    require([r["sequence"] for r in rows] == list(range(1, len(rows)+1)), "Trace loss/duplicate sequence")
    order = [(r["tick"], r["delta"]) for r in rows]
    require(order == sorted(order), "Trace time moved backwards")
    return rows


def normalize(rows, c, run_id, source="tlm"):
    first = int(c["clock"]["first_rising_tick"])
    period = int(c["clock"]["period_tick"])
    result = []
    for r in rows:
        event = {"schema_version": "1", "run_id": run_id, "source": source,
                 "event": r["event"], "scope": "wdt", "observed_tick": str(r["tick"]),
                 "effective_tick": str(r["tick"]), "delay_tick": "0",
                 "delta": str(r["delta"]), "sequence": str(r["sequence"]),
                 "value": str(r["value"]), "attributes": {"address": str(r["address"])}}
        if r["transaction_id"]:
            index = r["transaction_id"] - 1
            require(index < len(c["workload"]), "Unknown transaction ID")
            event["transaction_id"] = c["workload"][index]["id"]
            event["payload_bytes"] = 4
        if r["tick"] >= first and (r["tick"]-first) % period == 0:
            event.update(clock_id=c["clock"]["name"], epoch="0", cycle=str((r["tick"]-first)//period))
        result.append(event)
    return result


def write_jsonl(path, events):
    with exclusive_text(path) as f:
        for event in events:
            f.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")


def read_jsonl(path):
    events = [parse_json(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]
    require(bool(events), "Empty canonical events")
    previous = (-1, -1)
    for i, e in enumerate(events, 1):
        required = {"schema_version", "run_id", "source", "event", "scope", "observed_tick",
                    "effective_tick", "delay_tick", "delta", "sequence", "value", "attributes"}
        fields(e, required | {"transaction_id", "payload_bytes", "clock_id", "epoch", "cycle"}, required)
        require(e["schema_version"] == "1" and isinstance(e["event"], str) and e["event"] in KINDS,
                "Unsupported canonical event")
        require(all(isinstance(e[k], str) and e[k] for k in ("run_id", "source")), "Missing event provenance")
        def scalar(value, name, maximum=MAX_TICK):
            require(isinstance(value, str), f"{name}: canonical integers must be decimal strings")
            number = integer(value, name, 0, maximum)
            require(str(number) == value, f"{name}: non-canonical decimal string")
            return number
        require(scalar(e["sequence"], "sequence") == i, "Canonical sequence loss")
        tick, delta = scalar(e["observed_tick"], "observed_tick"), scalar(e["delta"], "delta", 2**64-1)
        require((tick, delta) >= previous and tick >= 0 and delta >= 0, "Canonical order")
        require(e.get("effective_tick") == e["observed_tick"] and e.get("delay_tick") == "0", "WDT effective time")
        require(e.get("scope") == "wdt" and isinstance(e.get("attributes"), dict), "Missing WDT event scope/attributes")
        fields(e["attributes"], {"address"}, {"address"})
        scalar(e["value"], "value", 2**32-1)
        scalar(e["attributes"]["address"], "address", 2**64-1)
        if e["event"] in TERMINAL | {"submit", "peq_ready"}:
            require(isinstance(e.get("transaction_id"), str) and bool(e["transaction_id"]), "Invalid transaction ID")
            require(type(e.get("payload_bytes")) is int and e["payload_bytes"] == 4, "Invalid register payload size")
        else:
            require("transaction_id" not in e and "payload_bytes" not in e, "Unexpected transaction identity")
        clock_fields = {"clock_id", "epoch", "cycle"}
        require(not (clock_fields & e.keys()) or clock_fields <= e.keys(), "Incomplete clock identity")
        if "clock_id" in e:
            require(isinstance(e["clock_id"], str) and bool(e["clock_id"]), "Invalid clock ID")
            scalar(e["epoch"], "epoch")
            scalar(e["cycle"], "cycle")
        if e["event"] not in {"submit", "peq_ready"}:
            require(clock_fields <= e.keys(), "Missing architectural clock identity")
        previous = tick, delta
    return events


def validate_lifecycles(events, c, check_timing=True):
    groups = {}
    for e in events:
        if "transaction_id" in e:
            groups.setdefault(e["transaction_id"], []).append(e)
        else:
            require(e["event"] in {"reset", "expiry", "irq", "reset_request"}, "Missing transaction ID")
    require(set(groups) == {op["id"] for op in c["workload"]}, "Missing/unexpected transactions")
    period, first = int(c["clock"]["period_tick"]), int(c["clock"]["first_rising_tick"])
    previous = 0
    for op in c["workload"]:
        rows = groups[op["id"]]
        require(len(rows) == 3 and rows[0]["event"] == "submit" and rows[1]["event"] == "peq_ready"
                and rows[2]["event"] in TERMINAL, f"Invalid lifecycle: {op['id']}")
        if rows[2]["event"] in {"commit_read", "commit_write"}:
            expected_kind = {"read32": "commit_read", "write32": "commit_write"}.get(op["op"])
            require(rows[2]["event"] == expected_kind, f"Completion operation mismatch: {op['id']}")
        submit, ready, commit = map(lambda e: int(e["observed_tick"]), rows)
        expected_submit = (previous + int(op.get("offset_tick", 0)) if "after_completion_of" in op
                           else int(op["offer_tick"]))
        if check_timing:
            require(submit == expected_submit, f"Offer mismatch: {op['id']}")
            require(ready == submit + int(op.get("delay_tick", 0)) + int(c["parameters"]["bus_latency_tick"]),
                    f"PEQ readiness mismatch: {op['id']}")
        expected = first if ready < first else first + ((ready-first)//period+1)*period
        if check_timing:
            require(commit == expected, f"Strict next-edge violation: {op['id']}")
        require(all(int(r["attributes"]["address"]) == address(op["address"]) for r in rows), "Address changed")
        previous = commit
    for e in events if check_timing else []:
        if e["event"] not in {"submit", "peq_ready"}:
            tick = int(e["observed_tick"])
            require(tick >= first and (tick-first) % period == 0, "Non-edge architectural event")
            require(e.get("clock_id") == c["clock"]["name"] and e.get("epoch") == "0"
                    and e.get("cycle") == str((tick-first)//period), "Clock identity/cycle mismatch")
    return groups


def compare_events(left, right, tolerance=0):
    tolerance = integer(tolerance, "tolerance")
    # Transaction identity and per-kind occurrence match independent observations.
    # Architectural order is checked separately within each timestamp batch;
    # delta/observation sequence are simulator-local, not cross-model keys.
    def keyed(events):
        counts, result = {}, {}
        for e in events:
            base = (e["scope"], e["event"], e.get("transaction_id", ""))
            n = counts.get(base, 0)
            counts[base] = n+1
            result[base + (n,)] = e
        return result
    a, b = keyed(left), keyed(right)
    differences = []
    maximum = 0
    for key in sorted(a.keys() | b.keys(), key=lambda k: (int((a.get(k) or b[k])["observed_tick"]), k)):
        x, y = a.get(key), b.get(key)
        reason = None
        if x is None or y is None:
            reason = "missing_event"
        else:
            delta = abs(int(x["observed_tick"])-int(y["observed_tick"]))
            maximum = max(maximum, delta)
            if delta > tolerance:
                reason = "timing"
            elif (x.get("value"), x.get("attributes")) != (y.get("value"), y.get("attributes")):
                reason = "value"
            elif x.get("clock_id") != y.get("clock_id") or x.get("epoch") != y.get("epoch"):
                reason = "clock_domain"
        if reason:
            differences.append({"key": key, "reason": reason, "left": x, "right": y})
    # Preserve order of dependent register completions and output transitions,
    # while allowing independent transaction rows to be interleaved.
    def architecture(events):
        return [(e["event"], e.get("transaction_id", ""), e.get("value")) for e in events
                if e["event"] in TERMINAL | {"reset", "expiry", "irq", "reset_request"}]
    if architecture(left) != architecture(right) and not differences:
        differences.append({"reason": "architectural_order"})
    return {"status": "fail" if differences else "pass", "mode": "exact_ticks" if not tolerance else "bounded_ticks",
            "tolerance_tick": str(tolerance), "maximum_discrepancy_tick": str(maximum),
            "mismatch_count": len(differences), "first_mismatch": differences[0] if differences else None,
            "differences": differences[:100]}
