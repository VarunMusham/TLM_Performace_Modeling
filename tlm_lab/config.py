"""Strict version-1 WDT adapter contract; integer ticks are 1 ns."""
import json
import re
from pathlib import Path

MAX_TICK = 2**63 - 2


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, allowed, required=()):
    require(isinstance(value, dict), "Expected a JSON object")
    require(not (set(value) - set(allowed)), f"Unknown fields: {set(value) - set(allowed)}")
    require(set(required) <= set(value), f"Missing fields: {set(required) - set(value)}")


def integer(value, name, low=0, high=MAX_TICK):
    require(type(value) is int or (isinstance(value, str) and re.fullmatch(r"[0-9]+", value)),
            f"{name}: expected an unsigned integer or decimal string")
    number = int(value)
    require(low <= number <= high, f"{name}: outside [{low}, {high}]")
    return number


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path):
    return validate(json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object))


def validate(c):
    fields(c, {"schema_version", "name", "adapter", "systemc_target", "clock", "parameters",
               "reset", "workload", "measurement", "trace", "seed", "expectations"},
           {"schema_version", "name", "adapter", "clock", "parameters", "reset", "workload", "measurement"})
    require(c["schema_version"] == "1", "schema_version must be '1'")
    require(c["adapter"] == "hybrid_wdt", "Only hybrid_wdt is registered")
    require(isinstance(c["name"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", c["name"]), "Invalid scenario name")
    require(c.get("systemc_target", "2.3.4") == "2.3.4", "SystemC target must be 2.3.4")
    fields(c["clock"], {"name", "period_tick", "first_rising_tick"}, {"name", "period_tick", "first_rising_tick"})
    require(isinstance(c["clock"]["name"], str) and bool(c["clock"]["name"]), "Missing clock name")
    period = integer(c["clock"]["period_tick"], "period", 2)
    first = integer(c["clock"]["first_rising_tick"], "first edge", 1)
    require(period % 2 == 0, "1 ns resolution requires an even clock period")
    fields(c["parameters"], {"bus_latency_tick"}, {"bus_latency_tick"})
    latency = integer(c["parameters"]["bus_latency_tick"], "bus latency")
    fields(c["measurement"], {"start_tick", "end_tick", "drain_deadline_tick"},
           {"start_tick", "end_tick", "drain_deadline_tick"})
    start, end, drain = (integer(c["measurement"][key], key) for key in
                         ("start_tick", "end_tick", "drain_deadline_tick"))
    require(start < end <= drain, "Require start < end <= drain")
    require(first <= drain, "No clock edge before drain")
    require(isinstance(c["reset"], list) and bool(c["reset"]), "reset must be a transition list")
    last = -1
    for transition in c["reset"]:
        fields(transition, {"tick", "reset_n"}, {"tick", "reset_n"})
        tick = integer(transition["tick"], "reset tick", 0, drain)
        require(tick > last and type(transition["reset_n"]) is bool, "Invalid reset transition order/level")
        require(tick < first or (tick-first) % period != 0, "Reset transition on sampling edge is ambiguous")
        last = tick
    require(not c["reset"][0]["reset_n"] and int(c["reset"][0]["tick"]) == 0, "Initial reset must be asserted at tick 0")
    require(len(c["reset"]) >= 2 and c["reset"][1]["reset_n"] and int(c["reset"][1]["tick"]) > first,
            "Initial reset must remain asserted through the first edge, then release")
    trace = c.get("trace", {"mode": "full", "max_events": 1000000})
    fields(trace, {"mode", "max_events"}, {"mode"})
    require(trace["mode"] in {"full", "off"}, "Trace mode must be full or off")
    integer(trace.get("max_events", 1000000), "max_events", 1)
    integer(c.get("seed", 0), "seed", 0, 2**32-1)
    require(isinstance(c["workload"], list) and bool(c["workload"]), "Empty workload")
    ids = set()
    previous = None
    completion = 0
    for op in c["workload"]:
        fields(op, {"id", "op", "offer_tick", "after_completion_of", "offset_tick", "address", "value",
                    "delay_tick", "length", "streaming_width", "byte_enable", "expect_status", "expect_value"},
               {"id", "op", "address"})
        require(isinstance(op["id"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", op["id"])
                and op["id"] not in ids, "Invalid or duplicate workload id")
        require(op["op"] in {"read32", "write32", "ignore"}, "Unsupported operation")
        require(("offer_tick" in op) != ("after_completion_of" in op), "Choose absolute offer or dependency")
        if "offer_tick" in op:
            require("offset_tick" not in op, "offset requires dependency")
            offered = integer(op["offer_tick"], "offer tick")
            require(offered >= completion, "Absolute offers overlap a blocking transaction")
        else:
            require(previous is not None and op["after_completion_of"] == previous,
                    "Dependency must name the immediately preceding operation")
            offered = completion + integer(op.get("offset_tick", 0), "offset")
        require(offered < end, "Every offer must precede measurement end (warm-up offers are allowed)")
        ready = offered + latency + integer(op.get("delay_tick", 0), "annotation")
        require(ready <= MAX_TICK, "Ready timestamp overflow")
        completion = first if ready < first else first + ((ready-first)//period + 1)*period
        address(op["address"])
        integer(op.get("value", 0), "value", 0, 2**32-1)
        integer(op.get("length", 4), "length", 0, 4)
        integer(op.get("streaming_width", 4), "streaming_width", 0, 2**32-1)
        require(type(op.get("byte_enable", False)) is bool, "byte_enable must be boolean")
        require(type(op.get("expect_status", 1)) is int and op.get("expect_status", 1) in {1, -1, -2, -3, -4, -5},
                "Invalid expected TLM status")
        if "expect_value" in op:
            integer(op["expect_value"], "expect_value", 0, 2**32-1)
        ids.add(op["id"])
        previous = op["id"]
    require(isinstance(c.get("expectations", []), list), "expectations must be a list")
    for e in c.get("expectations", []):
        fields(e, {"event", "ticks", "values"}, {"event", "ticks"})
        require(e["event"] in {"expiry", "irq", "reset_request", "reset"}, "Invalid expected event")
        require(isinstance(e["ticks"], list), "Expected ticks list")
        for tick in e["ticks"]:
            integer(tick, "expected tick", 0, drain)
        if "values" in e:
            require(isinstance(e["values"], list) and len(e["values"]) == len(e["ticks"]), "Expected values length")
            for value in e["values"]:
                integer(value, "expected value", 0, 2**32-1)
    return c


def address(value):
    if isinstance(value, str) and re.fullmatch(r"0x[0-9a-fA-F]+", value):
        value = int(value, 16)
    return integer(value, "address", 0, 2**64-1)


def write_workload(c, path):
    clock, m = c["clock"], c["measurement"]
    lines = [f"WDT1 {clock['period_tick']} {clock['first_rising_tick']} "
             f"{c['parameters']['bus_latency_tick']} {m['end_tick']} {m['drain_deadline_tick']}"]
    for r in c["reset"]:
        lines.append(f"reset {r['tick']} {int(r['reset_n'])}")
    for op in c["workload"]:
        relative = "after_completion_of" in op
        values = [{"read32": 0, "write32": 1, "ignore": 2}[op["op"]], int(relative),
                  op.get("offset_tick", 0) if relative else op["offer_tick"], address(op["address"]),
                  op.get("value", 0), op.get("delay_tick", 0), op.get("length", 4),
                  op.get("streaming_width", 4), int(op.get("byte_enable", False))]
        lines.append("op " + " ".join(map(str, values)))
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
