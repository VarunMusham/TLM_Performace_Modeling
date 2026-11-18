# Adapter integration template

For the implemented customer workflow, run `python tlm-lab.py init my-ip` or
`init my-ip --template cpp`, then follow the
[external adapter contract](../docs/EXTERNAL_ADAPTERS.md). This supports existing
source/testbench build commands without changing core platform code. The
checklist below remains useful for model-specific accuracy and timing review.

For each IP, document:

- Model owner/revision, build entry point, compiler/SystemC ABI, and dependencies.
- Socket types, custom payloads/phases/extensions, signals, and register interface.
- Address map, parameter ranges, clock domains, reset behavior, and setup sequence.
- Delay ownership, PEQ usage, temporal decoupling, response acceptance, and DMI.
- Queue capacities, outstanding limits, credits, arbitration, retry/reordering.
- Observable boundaries, stable IDs, supported metrics, and inaccessible internals.
- Workload/stop/drain semantics and configuration restrictions.
- RTL reference/export, agreed thresholds, and current qualification envelope.

Keep proprietary source in its existing location or ignored `private/`; record
its revision/hash in each run. Adapters should not rewrite the IP's latency model.
The initial WDT example lives in [examples/wdt](../examples/wdt/README.md).

