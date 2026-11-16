# RTL reference boundary

`wdt_reference.sv` independently implements the [WDT specification](../docs/WDT_SPEC.md)
with bus decode and clocked next-state equations. The CLI generates common-intent
stimulus, simulates with Icarus, samples after NBA updates, and exports reset,
transaction, expiry, IRQ and reset-request observations at integer edges.
Dependencies wait for actual RTL responses; C++ traces are never RTL stimulus.
[rtl.py](../tlm_lab/rtl.py) provides the bridge and normalizer.

Run `python -m tlm_lab run configs/wdt_scenario.example.json --rtl`. Generated
sources, compiled simulation, traces, responses, and first-mismatch reports stay
in the run directory. Passing applies to that experiment, not exhaustive formal
equivalence or production-IP qualification.

