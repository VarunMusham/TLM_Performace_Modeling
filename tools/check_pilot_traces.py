"""Check the fixed WDT pilot CSVs against independent timing expectations.

This is a pilot sanity checker, not an RTL correlation engine or generic analyzer.
Usage: python tools/check_pilot_traces.py build/traces
"""

import csv
from pathlib import Path
import sys


EXPECTED_EXPIRY = {
    "expiry": [80], "kick_boundary": [110], "disable_boundary": [],
    "reset_pending": [], "invalid": [], "annotated_delay": [],
    "read_counter": [80], "peq_on_edge": [],
}
TERMINAL = {"commit_read", "commit_write", "access_error", "reset_cancel"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(path, scenario):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    require(bool(rows), f"{path}: empty trace")
    fields = {"tick", "delta", "sequence", "event", "transaction_id", "address", "value"}
    require(set(rows[0]) == fields, f"{path}: wrong columns")
    for row in rows:
        for key in fields - {"event"}:
            row[key] = int(row[key])
    require([r["sequence"] for r in rows] == list(range(1, len(rows) + 1)), "Lost or duplicated observations")
    order = [(r["tick"], r["delta"]) for r in rows]
    require(order == sorted(order), "Observation order moved backwards")
    expiry = [r["tick"] for r in rows if r["event"] == "expiry"]
    require(expiry == EXPECTED_EXPIRY[scenario], f"{scenario}: expiry {expiry} differs from expected")

    groups = {}
    for row in rows:
        if row["transaction_id"]:
            groups.setdefault(row["transaction_id"], []).append(row)
    require(bool(groups), "No transactions observed")
    for tx_id, events in groups.items():
        require(len(events) == 3, f"Transaction {tx_id}: wrong observation count")
        start, ready, complete = events
        require(start["event"] == "submit" and ready["event"] == "peq_ready", "Bad request lifecycle")
        require(complete["event"] in TERMINAL, "Missing completion")
        annotation = 7 if scenario == "annotated_delay" else 4 if scenario == "peq_on_edge" else 0
        require(ready["tick"] == start["tick"] + 15 + annotation, "PEQ timing differs from contract")
        require(complete["tick"] == (ready["tick"] // 10 + 1) * 10, "Commit violated strict next-edge rule")
        require(len({r["address"] for r in events}) == 1, "Address changed in flight")
    if scenario == "reset_pending":
        require(sum(r["event"] == "reset_cancel" for r in rows) == 1, "Missing reset cancellation")
    if scenario == "read_counter":
        require(any(r["event"] == "commit_read" and r["address"] == 8 and r["value"] == 2 for r in rows), "Bad COUNT snapshot")
    for signal in ("irq", "reset_request"):
        assertions = [r["tick"] for r in rows if r["event"] == signal and r["value"] == 1]
        require(assertions == expiry, f"{signal} assertion differs from expiry")
    print(f"PASS {scenario}: {len(groups)} transactions; expiry ticks={expiry}")


def main():
    if len(sys.argv) != 2:
        raise ValueError("Usage: python tools/check_pilot_traces.py build/traces")
    directory = Path(sys.argv[1])
    for scenario in EXPECTED_EXPIRY:
        check(directory / f"{scenario}.csv", scenario)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)

