"""Replace the model/driver calls with your IP's actual source and testbench."""
import json
from pathlib import Path
import sys
from model import schedule

scenario_path, output, sdk = sys.argv[1:]
sys.path.insert(0, sdk)
from tlm_trace import TraceWriter

c = json.loads(Path(scenario_path).read_text(encoding="utf-8"))
operations = c["workload"]
ids = set()
previous = -1
for operation in operations:
    if not isinstance(operation.get("id"), str) or operation["id"] in ids:
        raise ValueError("Each operation needs a unique string id")
    ids.add(operation["id"])
    offered = int(operation["offer_tick"])
    if offered < previous or not 0 <= offered < int(c["measurement"]["end_tick"]):
        raise ValueError("Offers must be ordered and precede measurement end")
    if int(operation.get("work", 1)) <= 0 or int(operation["payload_bytes"]) < 0:
        raise ValueError("work must be positive; payload_bytes must be nonnegative")
    previous = offered
trace = TraceWriter(output)
for tick, event, txid, size in schedule(operations, **c["parameters"]):
    if tick > int(c["measurement"]["drain_deadline_tick"]):
        raise ValueError("Work remains after the drain deadline; increase the deadline")
    trace.emit(tick, event, txid, size)
trace.finish(int(c["measurement"]["drain_deadline_tick"]))
