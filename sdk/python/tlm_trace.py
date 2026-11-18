"""Copyable, standard-library-only transaction observer for customer testbenches."""
import csv
import json
from pathlib import Path


class TraceWriter:
    """Records observed model time; never schedules, waits or changes IP timing.

    Call finish only after successful simulation/drain. An exception leaves no
    completion marker, so partial traces cannot pass platform validation.
    """
    def __init__(self, directory):
        self.directory = Path(directory)
        self.stream = (self.directory/"transactions.csv").open("x", newline="", encoding="utf-8")
        self.writer = csv.writer(self.stream)
        self.writer.writerow(["sequence", "tick", "event", "transaction_id", "payload_bytes"])
        self.count = 0
        self.last_tick = 0

    def emit(self, tick, event, transaction_id, payload_bytes=None):
        if type(tick) is not int or tick < self.last_tick:
            raise ValueError("Observed ticks must be nonnegative, monotonic integers")
        self.count += 1
        self.last_tick = tick
        self.writer.writerow([self.count, tick, event, transaction_id, payload_bytes])

    def finish(self, stop_tick):
        if type(stop_tick) is not int or stop_tick < self.last_tick:
            raise ValueError("Capture stop precedes the last event")
        self.stream.flush()
        self.stream.close()
        with (self.directory/"completion.json").open("x", encoding="utf-8") as stream:
            json.dump({"schema_version": "capture-1", "finished": True, "event_count": self.count,
                       "loss_count": 0, "stop_tick": str(stop_tick)}, stream)
