# CLI platform components

The implementation is [tlm_lab](../tlm_lab/), invoked as `python -m tlm_lab`.
It includes strict validation, process isolation, manifests, canonical events,
metrics, independent WDT RTL comparison, reports, seeded sweeps, replay,
profiling, and regression. See [CLI](../docs/CLI.md) and
[architecture](../docs/ARCHITECTURE.md).

Source/testbench integration is available through
[external-1](../docs/EXTERNAL_ADAPTERS.md), with generic concurrent transaction
accounting, isolated builds and retained-source replay. Start with the
[customer guide](../docs/CUSTOMER_GUIDE.md). Protocol-specific adapters, internal
resource instrumentation and multi-IP topology authoring remain future work.

